"use client";

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { ButtonGroup } from '@/components/ui/button-group';
import { Copy, FolderOpen, Redo2, RefreshCw, Sparkles, Undo2, Wand2 } from 'lucide-react';
import Analytics from '@/lib/analytics';
import { RetranscribeDialog } from './RetranscribeDialog';
import { useConfig } from '@/contexts/ConfigContext';
import type { TranscriptEditorApi } from '@/hooks/meeting-details/useTranscriptEditor';
import { TranscriptFindReplace } from './TranscriptFindReplace';
import { Spinner } from '@/components/ui/spinner';

// One rule for every secondary button: icon only below lg, icon and label from lg up.
const LABEL = 'hidden lg:inline';


interface TranscriptButtonGroupProps {
  transcriptCount: number;
  onCopyTranscript: () => void;
  onOpenMeetingFolder: () => Promise<void>;
  meetingId?: string;
  meetingFolderPath?: string | null;
  onRefetchTranscripts?: () => Promise<void>;
  onSummarize?: () => void;
  // Present only while the transcript is editable (pre-push).
  editor?: TranscriptEditorApi;
}


export function TranscriptButtonGroup({
  transcriptCount,
  onCopyTranscript,
  onOpenMeetingFolder,
  meetingId,
  meetingFolderPath,
  onRefetchTranscripts,
  onSummarize,
  editor,
}: TranscriptButtonGroupProps) {
  const { betaFeatures } = useConfig();
  const [showRetranscribeDialog, setShowRetranscribeDialog] = useState(false);

  const handleRetranscribeComplete = useCallback(async () => {
    // Refetch transcripts to show the updated data
    if (onRefetchTranscripts) {
      await onRefetchTranscripts();
    }
  }, [onRefetchTranscripts]);

  return (
    <div className="flex w-full items-center justify-between gap-3">
      {/* Editing tools sit on the left, next to the text they change. */}
      <div className="flex items-center gap-2">
        {editor && (
          <>
            <ButtonGroup>
              <Button
                size="sm"
                variant="outline"
                disabled={!editor.canUndo}
                onClick={() => void editor.undo()}
                aria-label="Undo"
                title="Undo (⌘Z)"
              >
                <Undo2 />
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!editor.canRedo}
                onClick={() => void editor.redo()}
                aria-label="Redo"
                title="Redo (⌘⇧Z)"
              >
                <Redo2 />
              </Button>
            </ButtonGroup>
            <TranscriptFindReplace editor={editor} />
            <Button
              size="sm"
              variant="outline"
              disabled={editor.isSuggesting}
              aria-label="Proofread"
              title="Suggest fixes for misheard words"
              onClick={() => {
                Analytics.trackButtonClick('proofread_transcript', 'meeting_details');
                void editor.requestSuggestions();
              }}
            >
              {editor.isSuggesting ? <Spinner /> : <Wand2 />}
              <span className={LABEL}>{editor.isSuggesting ? 'Proofreading…' : 'Proofread'}</span>
            </Button>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        <ButtonGroup>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              Analytics.trackButtonClick('copy_transcript', 'meeting_details');
              onCopyTranscript();
            }}
            disabled={transcriptCount === 0}
            aria-label="Copy Transcript"
            title={transcriptCount === 0 ? 'No transcript to copy' : 'Copy Transcript'}
          >
            <Copy />
            <span className={LABEL}>Copy</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              Analytics.trackButtonClick('open_recording_folder', 'meeting_details');
              onOpenMeetingFolder();
            }}
            aria-label="Open Folder"
            title="Open the meeting's folder"
          >
            <FolderOpen />
            <span className={LABEL}>Open Folder</span>
          </Button>
          {betaFeatures.importAndRetranscribe && meetingId && meetingFolderPath && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                Analytics.trackButtonClick('enhance_transcript', 'meeting_details');
                setShowRetranscribeDialog(true);
              }}
              aria-label="Enhance"
              title="Re-transcribe the recording with another model or language"
            >
              <RefreshCw />
              <span className={LABEL}>Enhance</span>
            </Button>
          )}
        </ButtonGroup>

        {onSummarize && (
          // The screen's one primary action keeps its label at every width.
          <Button
            size="sm"
            onClick={() => {
              Analytics.trackButtonClick('open_summarize_dialog', 'meeting_details');
              onSummarize();
            }}
            disabled={transcriptCount === 0}
            title={transcriptCount === 0 ? 'No transcript to summarize' : 'Summarize meeting'}
          >
            <Sparkles />
            Summarize
          </Button>
        )}
      </div>

      {betaFeatures.importAndRetranscribe && meetingId && meetingFolderPath && (
        <RetranscribeDialog
          open={showRetranscribeDialog}
          onOpenChange={setShowRetranscribeDialog}
          meetingId={meetingId}
          meetingFolderPath={meetingFolderPath}
          onComplete={handleRetranscribeComplete}
        />
      )}
    </div>
  );
}
