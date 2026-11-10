"use client";
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Summary, SummaryResponse } from '@/types';
import { useSidebar, slugifyTag } from '@/components/Sidebar/SidebarProvider';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import Analytics from '@/lib/analytics';
import { TranscriptPanel } from '@/components/MeetingDetails/TranscriptPanel';
import { PushSummaryDialog } from '@/components/MeetingDetails/PushSummaryDialog';
import { PushedMeetingView } from '@/components/MeetingDetails/PushedMeetingView';

// Custom hooks
import { useMeetingData } from '@/hooks/meeting-details/useMeetingData';
import { useCopyOperations } from '@/hooks/meeting-details/useCopyOperations';
import { useMeetingOperations } from '@/hooks/meeting-details/useMeetingOperations';
import { useTranscriptEditor } from '@/hooks/meeting-details/useTranscriptEditor';

function formatDate(value: string | null | undefined, options: Intl.DateTimeFormatOptions): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : new Intl.DateTimeFormat(undefined, options).format(date);
}

/** "6 Nov 2026, 10:00 · 19 lines · Sent to Attio 6 Nov 2026": when, how much, and whether it was pushed. */
function meetingSummaryLine(createdAt: string, lineCount: number, pushedAt?: string | null, unnamedSpeakers = 0): string {
  const when = formatDate(createdAt, { dateStyle: 'medium', timeStyle: 'short' });
  const lines = `${new Intl.NumberFormat().format(lineCount)} ${lineCount === 1 ? 'line' : 'lines'}`;
  const sent = formatDate(pushedAt, { dateStyle: 'medium' });
  const toName = unnamedSpeakers > 0 && `${unnamedSpeakers} ${unnamedSpeakers === 1 ? 'speaker' : 'speakers'} to name`;
  return [when, lines, toName, sent && `Sent to Attio ${sent}`].filter(Boolean).join(' · ');
}

export default function PageContent({
  meeting,
  summaryData,
  onMeetingUpdated,
  onRefetchTranscripts,
  onReloadTranscripts,
  // Pagination props for efficient transcript loading
  segments,
  hasMore,
  isLoadingMore,
  totalCount,
  loadedCount,
  onLoadMore,
}: {
  meeting: any;
  summaryData: Summary | null;
  onMeetingUpdated?: () => Promise<void>;
  onRefetchTranscripts?: () => Promise<void>;
  onReloadTranscripts?: () => Promise<void>;
  // Pagination props
  segments?: any[];
  hasMore?: boolean;
  isLoadingMore?: boolean;
  totalCount?: number;
  loadedCount?: number;
  onLoadMore?: () => void;
}) {
  console.log('📄 PAGE CONTENT: Initializing with data:', {
    meetingId: meeting.id,
    summaryDataKeys: summaryData ? Object.keys(summaryData) : null,
    transcriptsCount: meeting.transcripts?.length
  });

  // State
  const [isRecording] = useState(false);
  const [summaryResponse] = useState<SummaryResponse | null>(null);
  const [showSummaryDialog, setShowSummaryDialog] = useState(false);
  const [unnamedSpeakers, setUnnamedSpeakers] = useState(0);

  // A meeting is locked for editing once it's been pushed to Scribe --
  // pushed_at is persisted so this holds across app restarts, not just
  // in-session state.
  const isPushed = Boolean(meeting.pushed_at);

  const router = useRouter();
  // Derived from the meeting's own tag rather than history, so Back can only ever lead to its folder.
  const folderName: string | undefined = meeting.push_tag?.trim() || undefined;

  const transcriptEditor = useTranscriptEditor({
    meetingId: meeting.id,
    segments: segments ?? [],
    editable: !isPushed,
    reload: onReloadTranscripts ?? (async () => {}),
  });

  // Sidebar context
  const { serverAddress } = useSidebar();

  // Custom hooks
  const meetingData = useMeetingData({ meeting, summaryData, onMeetingUpdated });

  const copyOperations = useCopyOperations({
    meeting,
    transcripts: meetingData.transcripts,
    meetingTitle: meetingData.meetingTitle,
    aiSummary: meetingData.aiSummary,
    blockNoteSummaryRef: meetingData.blockNoteSummaryRef,
  });

  const meetingOperations = useMeetingOperations({
    meeting,
  });

  // Track page view
  useEffect(() => {
    Analytics.trackPageView('meeting_details');
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="flex flex-col h-screen bg-muted "
    >
      <header className="border-b border-border bg-card px-4 py-3">
        {folderName && (
          <div className="flex">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-2 mb-1 h-7 max-w-xs text-muted-foreground"
                  onClick={() =>
                    router.push(`/folder?tag=${encodeURIComponent(slugifyTag(folderName))}&name=${encodeURIComponent(folderName)}`)
                  }
                >
                  <ArrowLeft />
                  <span className="truncate">{folderName}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Back to {folderName}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          </div>
        )}
        <h1 className="select-text truncate text-xl font-semibold text-foreground">{meeting.title}</h1>
        <p className="select-text text-sm text-muted-foreground tabular-nums">{meetingSummaryLine(meeting.created_at, totalCount ?? meetingData.transcripts.length, meeting.pushed_at, isPushed ? 0 : unnamedSpeakers)}</p>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {isPushed ? (
          <PushedMeetingView
            meetingId={meeting.id}
            folderPath={meeting.folder_path}
            transcripts={meetingData.transcripts}
            segments={segments}
            hasMore={hasMore}
            isLoadingMore={isLoadingMore}
            totalCount={totalCount}
            loadedCount={loadedCount}
            onLoadMore={onLoadMore}
            onCopyTranscript={copyOperations.handleCopyTranscript}
            onOpenMeetingFolder={meetingOperations.handleOpenMeetingFolder}
          />
        ) : (
          <TranscriptPanel
            transcripts={meetingData.transcripts}
            onCopyTranscript={copyOperations.handleCopyTranscript}
            onOpenMeetingFolder={meetingOperations.handleOpenMeetingFolder}
            isRecording={isRecording}
            disableAutoScroll={true}
            // Pagination props for efficient loading
            usePagination={true}
            segments={segments}
            hasMore={hasMore}
            isLoadingMore={isLoadingMore}
            totalCount={totalCount}
            loadedCount={loadedCount}
            onLoadMore={onLoadMore}
            // Retranscription props
            meetingId={meeting.id}
            meetingFolderPath={meeting.folder_path}
            onRefetchTranscripts={onRefetchTranscripts}
            // Editable pre-push, summarize opens the push/summary popup
            editable={!isPushed}
            editor={transcriptEditor}
            onSummarize={() => setShowSummaryDialog(true)}
            onUnnamedSpeakersChange={setUnnamedSpeakers}
          />
        )}
      </div>

      {!isPushed && (
        <PushSummaryDialog
          open={showSummaryDialog}
          onOpenChange={setShowSummaryDialog}
          meetingId={meeting.id}
          initialTag={meeting.push_tag}
          onSummarized={onMeetingUpdated}
        />
      )}
    </motion.div>
  );
}
