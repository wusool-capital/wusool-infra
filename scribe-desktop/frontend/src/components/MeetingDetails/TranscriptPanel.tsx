"use client";

import { Transcript, TranscriptSegmentData } from '@/types';
import { TranscriptView } from '@/components/TranscriptView';
import { VirtualizedTranscriptView } from '@/components/VirtualizedTranscriptView';
import { TranscriptButtonGroup } from './TranscriptButtonGroup';
import { TranscriptSelectionBar } from './TranscriptSelectionBar';
import type { TranscriptEditorApi } from '@/hooks/meeting-details/useTranscriptEditor';
import { useMemo } from 'react';
import { useMeetingSpeakers } from '@/hooks/useMeetingSpeakers';
import { Button } from '@/components/ui/button';

interface TranscriptPanelProps {
  transcripts: Transcript[];
  onCopyTranscript: () => void;
  onOpenMeetingFolder: () => Promise<void>;
  isRecording: boolean;
  disableAutoScroll?: boolean;

  // Optional pagination props (when using virtualization)
  usePagination?: boolean;
  segments?: TranscriptSegmentData[];
  hasMore?: boolean;
  isLoadingMore?: boolean;
  totalCount?: number;
  loadedCount?: number;
  onLoadMore?: () => void;

  // Retranscription props
  meetingId?: string;
  meetingFolderPath?: string | null;
  onRefetchTranscripts?: () => Promise<void>;

  // Editable transcript (pre-push only) + summarize entry point
  editable?: boolean;
  onEditSegment?: (id: string, text: string) => void | Promise<unknown>;
  editor?: TranscriptEditorApi;
  onSummarize?: () => void;
  // Hide the Copy/Recording/Enhance action bar entirely (e.g. inside a
  // read-only tab of an already-pushed meeting).
  showActions?: boolean;
}

export function TranscriptPanel({
  transcripts,
  onCopyTranscript,
  onOpenMeetingFolder,
  isRecording,
  disableAutoScroll = false,
  usePagination = false,
  segments,
  hasMore,
  isLoadingMore,
  totalCount,
  loadedCount,
  onLoadMore,
  meetingId,
  meetingFolderPath,
  onRefetchTranscripts,
  editable = false,
  onEditSegment,
  editor,
  onSummarize,
  showActions = true,
}: TranscriptPanelProps) {
  const speakers = useMeetingSpeakers(meetingId, onRefetchTranscripts);

  // Convert transcripts to segments if pagination is not used but we want virtualization
  const convertedSegments = useMemo(() => {
    if (usePagination && segments) {
      return segments;
    }
    // Convert transcripts to segments for virtualization
    return transcripts.map(t => ({
      id: t.id,
      timestamp: t.audio_start_time ?? 0,
      endTime: t.audio_end_time,
      text: t.text,
      confidence: t.confidence,
      speaker: t.speaker,
    }));
  }, [transcripts, usePagination, segments]);

  return (
    <div className="flex w-full h-full min-w-0 bg-card flex-col relative">
      {/* Toolbar */}
      {showActions && (
        <div className="p-4 border-b border-border ">
          <TranscriptButtonGroup
            transcriptCount={usePagination ? (totalCount ?? convertedSegments.length) : (transcripts?.length || 0)}
            onCopyTranscript={onCopyTranscript}
            onOpenMeetingFolder={onOpenMeetingFolder}
            meetingId={meetingId}
            meetingFolderPath={meetingFolderPath}
            onRefetchTranscripts={onRefetchTranscripts}
            onSummarize={onSummarize}
            editor={editable ? editor : undefined}
          />
        </div>
      )}

      {editable && editor && editor.suggestions.size > 0 && (
        <div className="flex items-center justify-between gap-3 border-b border-border bg-muted px-4 py-2">
          <span className="text-sm text-foreground tabular-nums" aria-live="polite">
            {editor.suggestions.size} suggested {editor.suggestions.size === 1 ? 'fix' : 'fixes'}
          </span>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={editor.dismissAllSuggestions}>
              Dismiss All
            </Button>
            <Button size="sm" variant="outline" onClick={() => void editor.acceptAllSuggestions()}>
              Accept All
            </Button>
          </div>
        </div>
      )}

      {/* Transcript content - use virtualized view for better performance */}
      <div className="flex-1 overflow-hidden pb-4">
        <VirtualizedTranscriptView
          segments={convertedSegments}
          isRecording={isRecording}
          isPaused={false}
          isProcessing={false}
          isStopping={false}
          enableStreaming={false}
          showConfidence={true}
          disableAutoScroll={disableAutoScroll}
          hasMore={hasMore}
          isLoadingMore={isLoadingMore}
          totalCount={totalCount}
          loadedCount={loadedCount}
          onLoadMore={onLoadMore}
          editable={editable}
          onEditSegment={onEditSegment}
          editor={editable ? editor : undefined}
          speakers={speakers}
        />
      </div>

      {editable && editor && <TranscriptSelectionBar editor={editor} />}
    </div>
  );
}
