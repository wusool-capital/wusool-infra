"use client";

import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { FolderOpen, FileText, ListChecks, Mic, Copy, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Transcript, TranscriptSegmentData } from '@/types';
import { TranscriptPanel } from './TranscriptPanel';
import { SummaryView } from './SummaryView';
import { summaryToPlainText } from '@/lib/pushedSummary';
import { ScrollArea } from '@/components/ui/scroll-area';

interface PushedMeetingViewProps {
  meetingId: string;
  folderPath?: string | null;
  transcripts: Transcript[];
  segments?: TranscriptSegmentData[];
  hasMore?: boolean;
  isLoadingMore?: boolean;
  totalCount?: number;
  loadedCount?: number;
  onLoadMore?: () => void;
  onCopyTranscript: () => void;
  onOpenMeetingFolder: () => Promise<void>;
}

/**
 * View for a meeting that has already been pushed and summarized --
 * no editing, no Summarize button (push is one-shot). Splits Summary,
 * Transcript, and Recording into their own tabs instead of the
 * transcript-first layout used before a push.
 */
export function PushedMeetingView({
  meetingId,
  folderPath,
  transcripts,
  segments,
  hasMore,
  isLoadingMore,
  totalCount,
  loadedCount,
  onLoadMore,
  onCopyTranscript,
  onOpenMeetingFolder,
}: PushedMeetingViewProps) {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const [tab, setTab] = useState('summary');

  const loadSummary = useCallback(async () => {
    try {
      const result = await invoke('get_saved_summary', { meetingId });
      setSummary((result as Record<string, unknown> | null) ?? null);
    } catch (error) {
      console.error('Failed to load saved summary:', error);
    }
  }, [meetingId]);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingSummary(true);
    loadSummary().finally(() => {
      if (!cancelled) setIsLoadingSummary(false);
    });
    return () => {
      cancelled = true;
    };
  }, [loadSummary]);

  useEffect(() => {
    // The background sync timer (lib.rs) can file this meeting's summary
    // while this view is open and showing the "No summary available
    // yet" dead end -- re-read it from disk instead of leaving the user
    // to navigate away and back.
    const unlisten = listen<number>('pushed-summaries-synced', () => {
      loadSummary();
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [loadSummary]);

  const handleCheckNow = async () => {
    setIsChecking(true);
    try {
      const result = (await invoke('sync_pushed_meetings')) as { synced: number; error?: string | null };
      await loadSummary();
      if (result.error) {
        toast.error(result.error);
      } else if (result.synced === 0) {
        toast.info('No new summary yet. Scribe may still be processing it.');
      }
    } catch (error) {
      console.error('Failed to check for summary:', error);
      toast.error('Failed to check for summary');
    } finally {
      setIsChecking(false);
    }
  };

  const handleCopySummary = async () => {
    if (!summary) return;
    try {
      await navigator.clipboard.writeText(summaryToPlainText(summary));
      toast.success('Summary copied');
    } catch (error) {
      console.error('Failed to copy summary:', error);
      toast.error("Couldn't copy the summary. Try again.");
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-card ">
      <Tabs value={tab} onValueChange={setTab} className="flex flex-col h-full">
        <div className="flex items-center justify-between gap-3 border-b border-border p-4">
          <TabsList>
            <TabsTrigger value="summary" className="gap-1.5">
              <ListChecks size={14} /> Summary
            </TabsTrigger>
            <TabsTrigger value="transcript" className="gap-1.5">
              <FileText size={14} /> Transcript
            </TabsTrigger>
            <TabsTrigger value="recording" className="gap-1.5">
              <Mic size={14} /> Recording
            </TabsTrigger>
          </TabsList>
          {/* Copy belongs to the summary, so it only shows while that tab is open. */}
          {tab === 'summary' && summary && (
            <Button size="sm" variant="outline" onClick={() => void handleCopySummary()} aria-label="Copy Summary">
              <Copy />
              <span className="hidden lg:inline">Copy</span>
            </Button>
          )}
        </div>

        <TabsContent value="summary" className="flex-1 min-h-0 mt-0">
          <ScrollArea className="h-full">
            <div className="p-6">
              {isLoadingSummary ? (
                <p className="text-sm text-muted-foreground">Loading summary…</p>
              ) : summary ? (
                <SummaryView summary={summary} />
              ) : (
                <div className="flex flex-col items-start gap-3">
                  <p className="text-sm text-muted-foreground">
                    No summary available yet. Scribe may still be processing it.
                  </p>
                  <Button size="sm" variant="outline" onClick={handleCheckNow} disabled={isChecking}>
                    <RefreshCw size={14} className={isChecking ? 'motion-safe:animate-spin' : undefined} />
                    <span>{isChecking ? 'Checking…' : 'Check Now'}</span>
                  </Button>
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="transcript" className="flex-1 overflow-hidden mt-0">
          <TranscriptPanel
            transcripts={transcripts}
            onCopyTranscript={onCopyTranscript}
            onOpenMeetingFolder={onOpenMeetingFolder}
            isRecording={false}
            disableAutoScroll={true}
            usePagination={true}
            segments={segments}
            hasMore={hasMore}
            isLoadingMore={isLoadingMore}
            totalCount={totalCount}
            loadedCount={loadedCount}
            onLoadMore={onLoadMore}
            meetingId={meetingId}
            meetingFolderPath={folderPath}
            editable={false}
            showActions={false}
          />
        </TabsContent>

        <TabsContent value="recording" className="flex-1 min-h-0 mt-0">
          <ScrollArea className="h-full">
            <section className="max-w-[70ch] space-y-3 p-6">
              <h2 className="text-base font-semibold text-foreground">Recording Folder</h2>
              <p className="select-text break-all text-sm text-muted-foreground">
                {folderPath || 'This meeting has no recording folder.'}
              </p>
              <Button size="sm" variant="outline" onClick={onOpenMeetingFolder} disabled={!folderPath}>
                <FolderOpen size={16} />
                Open Folder
              </Button>
            </section>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
