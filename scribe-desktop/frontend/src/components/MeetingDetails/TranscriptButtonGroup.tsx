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
    <div className="flex items-center justify-between w-full gap-2">
      <ButtonGroup>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            Analytics.trackButtonClick('copy_transcript', 'meeting_details');
            onCopyTranscript();
          }}
          disabled={transcriptCount === 0}
          title={transcriptCount === 0 ? 'No transcript available' : 'Copy Transcript'}
        >
          <Copy />
          <span className="hidden lg:inline">Copy</span>
        </Button>

        <Button
          size="sm"
          variant="outline"
          className="xl:px-4"
          onClick={() => {
            Analytics.trackButtonClick('open_recording_folder', 'meeting_details');
            onOpenMeetingFolder();
          }}
          title="Open Recording Folder"
        >
          <FolderOpen className="xl:mr-2" size={18} />
          <span className="hidden lg:inline">Recording</span>
        </Button>

        {betaFeatures.importAndRetranscribe && meetingId && meetingFolderPath && (
          <Button
            size="sm"
            variant="outline"
            className="bg-gradient-to-r from-primary/10 to-purple-50 dark:to-purple-950 hover:from-primary/15 hover:to-purple-100 dark:hover:to-purple-900 border-primary/30 text-foreground xl:px-4"
            onClick={() => {
              Analytics.trackButtonClick('enhance_transcript', 'meeting_details');
              setShowRetranscribeDialog(true);
            }}
            title="Retranscribe to enhance your recorded audio"
          >
            <RefreshCw className="xl:mr-2" size={18} />
            <span className="hidden lg:inline">Enhance</span>
          </Button>
        )}
      </ButtonGroup>

      {editor && (
        <div className="flex items-center gap-2">
          <ButtonGroup>
            <Button
              size="sm"
              variant="outline"
              disabled={!editor.canUndo}
              onClick={() => void editor.undo()}
              title="Undo (Cmd+Z)"
            >
              <Undo2 size={16} />
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!editor.canRedo}
              onClick={() => void editor.redo()}
              title="Redo (Cmd+Shift+Z)"
            >
              <Redo2 size={16} />
            </Button>
          </ButtonGroup>
          <TranscriptFindReplace editor={editor} />
          {/* Shipped disabled until suggestion quality is validated on real transcripts. */}
          <Button size="sm" variant="outline" disabled title="Suggest fixes for misheard words: coming soon">
            <Wand2 size={16} />
            <span className="hidden xl:inline">Suggest fixes</span>
            <span className="hidden text-xs text-muted-foreground xl:inline">Coming soon</span>
          </Button>
        </div>
      )}

      {onSummarize && (
        <Button
          size="sm"
          onClick={() => {
            Analytics.trackButtonClick('open_summarize_dialog', 'meeting_details');
            onSummarize();
          }}
          disabled={transcriptCount === 0}
          title={transcriptCount === 0 ? 'No transcript available' : 'Summarize meeting'}
        >
          <Sparkles size={16} />
          <span className="hidden lg:inline">Summarize</span>
        </Button>
      )}

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
