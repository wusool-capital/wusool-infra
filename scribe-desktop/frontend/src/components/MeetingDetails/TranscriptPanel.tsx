"use client";

import { Transcript, TranscriptSegmentData } from '@/types';
import { TranscriptView } from '@/components/TranscriptView';
import { VirtualizedTranscriptView } from '@/components/VirtualizedTranscriptView';
import { TranscriptButtonGroup } from './TranscriptButtonGroup';
import { TranscriptSelectionBar } from './TranscriptSelectionBar';
import type { TranscriptEditorApi } from '@/hooks/meeting-details/useTranscriptEditor';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useMeetingSpeakers } from '@/hooks/useMeetingSpeakers';
import { SpeakersPanel } from '@/components/SpeakersPanel';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { nameChanges, nextSuggestionId, proofreadCoverageWarning, type NameChange } from '@/lib/transcriptEditor';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { useCoreMlModels } from '@/hooks/useCoreMlModels';
import { CoreMlDownloadDialog } from '@/components/CoreMlDownloadDialog';

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
  /** Voices still waiting for a name, for the meeting header; editable meetings only. */
  onUnnamedSpeakersChange?: (count: number) => void;
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
  onUnnamedSpeakersChange,
}: TranscriptPanelProps) {
  const speakers = useMeetingSpeakers(meetingId, onRefetchTranscripts);
  const [focusRequest, setFocusRequest] = useState<{ segmentId: string; nonce: number }>();

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

  const unnamedCount = speakers.overview.filter((voice) => voice.name === null).length;
  useEffect(() => {
    if (editable) onUnnamedSpeakersChange?.(unnamedCount);
  }, [editable, unnamedCount, onUnnamedSpeakersChange]);

  // Edits, tidying and deletes change talk time and sample lines; a short delay batches a burst of edits.
  const { refresh } = speakers;
  const editRevision = editor?.revision ?? 0;
  useEffect(() => {
    if (!editable || editRevision === 0) return;
    const timer = setTimeout(() => void refresh(), 400);
    return () => clearTimeout(timer);
  }, [editable, editRevision, refresh]);

  const hasUnseparatedLines = useMemo(
    () => convertedSegments.some((segment) => segment.speaker === 'others'),
    [convertedSegments],
  );
  const showSeparateBanner = Boolean(editable && speakers.separate && speakers.voiceCount === 0 && hasUnseparatedLines);

  // Loaded only while the banner shows, so opening a meeting costs nothing extra.
  const coreMl = useCoreMlModels(showSeparateBanner);
  // CoreML is the default, but its models download only when asked: offer that here first.
  const separateSpeakers = () => {
    if (coreMl.needsDownload) coreMl.ask();
    else void speakers.separate?.();
  };
  // Choosing the slower model turns CoreML off, so this prompt doesn't come back.
  const useSlowerModel = async () => {
    try {
      await coreMl.setBackend('cpu');
    } catch (error) {
      toast.error("Couldn't switch to the slower model", { description: String(error) });
    }
    await speakers.separate?.();
  };

  // Fixes that change a name are the ones most likely to be wrong, so Accept All shows them first.
  const [pendingNameChanges, setPendingNameChanges] = useState<NameChange[] | null>(null);
  const requestAcceptAll = () => {
    if (!editor) return;
    const changes = nameChanges(editor.suggestions.values());
    if (changes.length > 0) setPendingNameChanges(changes);
    else void editor.acceptAllSuggestions();
  };

  // Steps through the suggested fixes in transcript order from the last one shown.
  const lastFixRef = useRef<string | null>(null);
  const segmentOrder = useMemo(() => convertedSegments.map((segment) => segment.id), [convertedSegments]);
  const showNextFix = () => {
    const ids = editor ? [...editor.suggestions.keys()] : [];
    const segmentId = nextSuggestionId(ids, segmentOrder, lastFixRef.current);
    if (!segmentId) return;
    lastFixRef.current = segmentId;
    setFocusRequest({ segmentId, nonce: Date.now() });
  };

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

      {showSeparateBanner && (
        <div className="flex items-center justify-between gap-3 border-b border-border bg-muted px-4 py-2">
          <span className="min-w-0 text-sm text-foreground" aria-live="polite">
            {speakers.separation.status === 'running'
              ? 'Separating speakers…'
              : speakers.separation.status === 'failed'
                ? `Couldn't separate speakers: ${speakers.separation.error}`
                : "Other speakers haven't been separated yet."}
          </span>
          {speakers.separation.status === 'running' ? (
            <Spinner className="h-4 w-4 shrink-0" />
          ) : (
            <Button size="sm" variant="outline" onClick={separateSpeakers}>
              {speakers.separation.status === 'failed' ? 'Try Again' : 'Separate Speakers'}
            </Button>
          )}
        </div>
      )}

      <CoreMlDownloadDialog
        coreMl={coreMl}
        description="Separate speakers about 6× faster with a one-time download of about 300 MB. Or use the slower model, which needs no download. You can switch back in Settings."
        skipLabel="Use Slower Model (6× Slower)"
        onSkip={() => void useSlowerModel()}
        onDownloaded={() => void speakers.separate?.()}
      />

      {editable && meetingId && (
        <SpeakersPanel
          meetingId={meetingId}
          speakers={speakers}
          onShowLine={(segmentId) => setFocusRequest({ segmentId, nonce: Date.now() })}
        />
      )}

      {editable && editor && (editor.suggestions.size > 0 || editor.uncheckedLines > 0) && (
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-border bg-muted px-4 py-2">
          <p className="text-sm text-foreground tabular-nums" aria-live="polite">
            {editor.suggestions.size > 0
              ? `${editor.suggestions.size} suggested ${editor.suggestions.size === 1 ? 'fix' : 'fixes'}`
              : 'No suggested fixes'}
            {editor.uncheckedLines > 0 && (
              <span className="text-muted-foreground"> · {proofreadCoverageWarning(editor.uncheckedLines)}</span>
            )}
          </p>
          <div className="flex items-center gap-2">
            {editor.uncheckedLines > 0 && (
              <Button
                size="sm"
                variant="ghost"
                disabled={editor.isSuggesting}
                onClick={() => void editor.retryUnchecked()}
              >
                {editor.isSuggesting ? 'Proofreading…' : 'Try Again'}
              </Button>
            )}
            {editor.suggestions.size > 1 && (
              <Button size="sm" variant="ghost" onClick={showNextFix}>
                Next Fix
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={editor.dismissAllSuggestions}>
              Dismiss All
            </Button>
            {editor.suggestions.size > 0 && (
              <Button size="sm" variant="outline" onClick={requestAcceptAll}>
                Accept All
              </Button>
            )}
          </div>
        </div>
      )}

      <AlertDialog open={pendingNameChanges !== null} onOpenChange={(open) => !open && setPendingNameChanges(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apply Name Changes?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingNameChanges?.length === 1 ? 'One fix changes a name.' : `${pendingNameChanges?.length} fixes change names.`}{' '}
              Check they are the same person before applying them all.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
            {pendingNameChanges?.map((change, i) => (
              <li key={i}>
                {change.from ? <del className="text-destructive">{change.from}</del> : <span className="text-muted-foreground">(added)</span>}
                <span className="text-muted-foreground"> → </span>
                <ins className="font-semibold text-success no-underline">{change.to}</ins>
              </li>
            ))}
          </ul>
          <AlertDialogFooter>
            <AlertDialogCancel>Review One by One</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setPendingNameChanges(null);
                void editor?.acceptAllSuggestions();
              }}
            >
              Apply All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
          focusRequest={focusRequest}
        />
      </div>

      {editable && editor && <TranscriptSelectionBar editor={editor} />}
    </div>
  );
}
