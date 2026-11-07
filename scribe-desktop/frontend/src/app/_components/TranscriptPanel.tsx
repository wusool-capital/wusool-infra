import { VirtualizedTranscriptView } from '@/components/VirtualizedTranscriptView';
import { PermissionWarning } from '@/components/PermissionWarning';
import { Button } from '@/components/ui/button';
import { ButtonGroup } from '@/components/ui/button-group';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Copy, GlobeIcon } from 'lucide-react';
import { useTranscripts } from '@/contexts/TranscriptContext';
import { useConfig } from '@/contexts/ConfigContext';
import { useRecordingState } from '@/contexts/RecordingStateContext';
import { usePermissionCheck } from '@/hooks/usePermissionCheck';
import { ModalType } from '@/hooks/useModalState';
import { useIsLinux } from '@/hooks/usePlatform';
import { useMemo } from 'react';
import { useMeetingSpeakers } from '@/hooks/useMeetingSpeakers';
import { ScrollArea } from '@/components/ui/scroll-area';
import Link from 'next/link';

/**
 * TranscriptPanel Component
 *
 * Displays transcript content with controls for copying and language settings.
 * Uses TranscriptContext, ConfigContext, and RecordingStateContext internally.
 */

interface TranscriptPanelProps {
  // indicates stop-processing state for transcripts; derived from backend statuses.
  isProcessingStop: boolean;
  isStopping: boolean;
  showModal: (name: ModalType, message?: string) => void;
}

export function TranscriptPanel({
  isProcessingStop,
  isStopping,
  showModal
}: TranscriptPanelProps) {
  // Contexts
  const { transcripts, transcriptContainerRef, copyTranscript } = useTranscripts();
  const { transcriptModelConfig, selectedDevices } = useConfig();
  const { isRecording, isPaused } = useRecordingState();
  const { checkPermissions, isChecking, hasSystemAudio, hasMicrophone } = usePermissionCheck();
  const isLinux = useIsLinux();
  // Live transcripts only know "me" vs "others"; voices are separated after the meeting is saved.
  const speakers = useMeetingSpeakers();

  const showLanguage = transcriptModelConfig.provider === 'localWhisper';
  // The toolbar row only exists when it has a button, so it never leaves an empty band.
  const hasToolbar = transcripts.length > 0 || showLanguage;
  const isIdle = !isRecording && transcripts.length === 0;

  // Convert transcripts to segments for virtualized view
  const segments = useMemo(() =>
    transcripts.map(t => ({
      id: t.id,
      timestamp: t.audio_start_time ?? 0,
      endTime: t.audio_end_time,
      text: t.text,
      confidence: t.confidence,
      speaker: t.speaker,
    })),
    [transcripts]
  );

  // [&>div>div]:!block overrides Radix's inline display:table content wrapper,
  // which otherwise re-parents these children into anonymous table cells and
  // silently kills the sticky header below.
  return (
    <ScrollArea
      viewportRef={transcriptContainerRef}
      className="w-full h-full border-r border-border bg-background min-h-0 [&>div>div]:!block"
    >
      {hasToolbar ? (
        <div className="sticky top-0 z-10 flex justify-center bg-background p-4">
          <ButtonGroup>
            {transcripts.length > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="sm" onClick={copyTranscript} aria-label="Copy Transcript">
                    <Copy />
                    <span className="hidden md:inline">Copy</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Copy Transcript</TooltipContent>
              </Tooltip>
            )}
            {showLanguage && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="sm" onClick={() => showModal('languageSettings')} aria-label="Language">
                    <GlobeIcon />
                    <span className="hidden md:inline">Language</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Language</TooltipContent>
              </Tooltip>
            )}
          </ButtonGroup>
        </div>
      ) : null}
      {!isIdle && <h1 className="sr-only">Live Transcript</h1>}

      {/* Permission Warning - Not needed on Linux */}
      {!isRecording && !isChecking && !isLinux && (
        <div className="flex justify-center px-4 pt-4">
          <PermissionWarning
            hasMicrophone={hasMicrophone}
            hasSystemAudio={hasSystemAudio}
            onRecheck={checkPermissions}
            isRechecking={isChecking}
          />
        </div>
      )}

      {/* Transcript content */}
      <div className="pb-20">
        <div className="flex justify-center">
          <div className="w-2/3 max-w-[750px]">
            <VirtualizedTranscriptView
              segments={segments}
              isRecording={isRecording}
              isPaused={isPaused}
              isProcessing={isProcessingStop}
              isStopping={isStopping}
              enableStreaming={isRecording}
              showConfidence={true}
              speakers={speakers}
              emptyState={
                <section className="mx-auto mt-16 max-w-md space-y-6">
                  <div>
                    <h1 className="text-2xl font-semibold text-foreground">Record a Meeting</h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Scribe transcribes on this Mac as people speak. Your lines carry your name, and other voices are
                      separated when you stop.
                    </p>
                  </div>
                  <dl className="divide-y divide-border rounded-lg border border-border bg-card text-sm">
                    <div className="flex items-center justify-between gap-4 px-4 py-3">
                      <dt className="text-muted-foreground">Microphone</dt>
                      <dd className="min-w-0 truncate text-foreground">{selectedDevices.micDevice ?? 'System default'}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-4 px-4 py-3">
                      <dt className="text-muted-foreground">System Audio</dt>
                      <dd className="min-w-0 truncate text-foreground">{selectedDevices.systemDevice ?? 'System default'}</dd>
                    </div>
                  </dl>
                  <p className="text-sm text-muted-foreground">
                    Change these in{' '}
                    <Link href="/settings?tab=recording" className="text-foreground underline underline-offset-4">
                      Recording Settings
                    </Link>
                    .
                  </p>
                </section>
              }
            />
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}
