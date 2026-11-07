'use client';

import { invoke } from '@tauri-apps/api/core';
import { appDataDir } from '@tauri-apps/api/path';
import { useCallback, useEffect, useState, useRef } from 'react';
import { Play, Pause, Square, Mic, AlertCircle, X } from 'lucide-react';
import { ProcessRequest, SummaryResponse } from '@/types/summary';
import { listen } from '@tauri-apps/api/event';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { TooltipProvider } from '@/components/ui/tooltip';
import { Progress } from '@/components/ui/progress';
import { Spinner } from '@/components/ui/spinner';
import { StatusMessage } from '@/components/StatusMessage';
import Analytics from '@/lib/analytics';
import { useRecordingState } from '@/contexts/RecordingStateContext';
import { useMicLevel } from '@/hooks/useMicLevel';
import { formatElapsed } from '@/lib/formatElapsed';

interface RecordingControlsProps {
  isRecording: boolean;
  onRecordingStop: (callApi?: boolean) => void;
  onRecordingStart: () => void;
  onTranscriptReceived: (summary: SummaryResponse) => void;
  onTranscriptionError?: (message: string) => void;
  onStopInitiated?: () => void; // Called immediately when stop button is clicked
  isRecordingDisabled: boolean;
  isParentProcessing: boolean;
  selectedDevices?: {
    micDevice: string | null;
    systemDevice: string | null;
  };
  meetingName?: string;
}

export const RecordingControls: React.FC<RecordingControlsProps> = ({
  isRecording,
  onRecordingStop,
  onRecordingStart,
  onTranscriptReceived,
  onTranscriptionError,
  onStopInitiated,
  isRecordingDisabled,
  isParentProcessing,
  selectedDevices,
  meetingName,
}) => {
  // Use global recording state context for pause state (syncs with tray operations)
  const recordingState = useRecordingState();
  const isPaused = recordingState.isPaused;
  const isStarting = recordingState.isStarting;
  const micLevels = useMicLevel(isRecording && !isPaused);

  const [showPlayback, setShowPlayback] = useState(false);
  const [recordingPath, setRecordingPath] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isPausing, setIsPausing] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  // Transitions show in the status text so the change is announced, not just a floating label.
  const statusLabel = isStopping
    ? 'Stopping…'
    : isPausing
      ? 'Pausing…'
      : isResuming
        ? 'Resuming…'
        : isPaused
          ? 'Paused'
          : 'Recording';
  const MIN_RECORDING_DURATION = 2000; // 2 seconds minimum recording time
  const [transcriptionErrors, setTranscriptionErrors] = useState(0);
  const [isValidatingModel, setIsValidatingModel] = useState(false);
  const [speechDetected, setSpeechDetected] = useState(false);
  const [deviceError, setDeviceError] = useState<{ title: string, message: string } | null>(null);

  const currentTime = 0;
  const duration = 0;
  const isPlaying = false;
  const progress = 0;

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    const checkTauri = async () => {
      try {
        const result = await invoke('is_recording');
        console.log('Tauri is initialized and ready, is_recording result:', result);
      } catch (error) {
        console.error('Tauri initialization error:', error);
        alert('Failed to initialize recording. Please check the console for details.');
      }
    };
    checkTauri();
  }, []);

  const handleStartRecording = useCallback(async () => {
    if (isStarting || isValidatingModel) return;
    console.log('Starting recording...');
    console.log('Selected devices:', selectedDevices);
    console.log('Meeting name:', meetingName);
    console.log('Current isRecording state:', isRecording);

    setShowPlayback(false);
    setTranscript(''); // Clear any previous transcript
    setSpeechDetected(false); // Reset speech detection on new recording

    try {
      // Call the validation callback which will:
      // 1. Check if model is ready
      // 2. Show appropriate toast/modal
      // 3. Call backend if valid
      // 4. Update UI state
      await onRecordingStart();
    } catch (error) {
      console.error('Failed to start recording:', error);
      console.error('Error details:', {
        message: error instanceof Error ? error.message : String(error),
        name: error instanceof Error ? error.name : 'Unknown',
        stack: error instanceof Error ? error.stack : undefined
      });

      // Parse error message to provide user-friendly feedback
      const errorMsg = error instanceof Error ? error.message : String(error);

      // Check for device-related errors
      if (errorMsg.includes('microphone') || errorMsg.includes('mic') || errorMsg.includes('input')) {
        setDeviceError({
          title: 'Microphone Not Available',
          message: 'Unable to access your microphone. Please check that:\n• Your microphone is connected\n• The app has microphone permissions\n• No other app is using the microphone'
        });
      } else if (errorMsg.includes('system audio') || errorMsg.includes('speaker') || errorMsg.includes('output')) {
        setDeviceError({
          title: 'System Audio Not Available',
          message: 'Unable to capture system audio. Please check that:\n• A virtual audio device (like BlackHole) is installed\n• The app has screen recording permissions (macOS)\n• System audio is properly configured'
        });
      } else if (errorMsg.includes('permission')) {
        setDeviceError({
          title: 'Permission Required',
          message: 'Recording permissions are required. Please:\n• Grant microphone access in System Settings\n• Grant screen recording access for system audio (macOS)\n• Restart the app after granting permissions'
        });
      } else {
        setDeviceError({
          title: 'Recording Failed',
          message: 'Unable to start recording. Please check your audio device settings and try again.'
        });
      }
    }
  }, [onRecordingStart, isStarting, isValidatingModel, selectedDevices, meetingName, isRecording]);

  const stopRecordingAction = useCallback(async () => {
    console.log('Executing stop recording...');
    try {
      setIsProcessing(true);
      const dataDir = await appDataDir();
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const savePath = `${dataDir}/recording-${timestamp}.wav`;
      console.log('Saving recording to:', savePath);
      console.log('About to call stop_recording command');
      const result = await invoke('stop_recording', {
        args: {
          save_path: savePath
        }
      });
      console.log('stop_recording command completed successfully:', result);
      setRecordingPath(savePath);
      // setShowPlayback(true);
      setIsProcessing(false);
      // Track successful transcription
      Analytics.trackTranscriptionSuccess();
      onRecordingStop(true);
    } catch (error) {
      console.error('Failed to stop recording:', error);
      if (error instanceof Error) {
        console.error('Error details:', {
          message: error.message,
          name: error.name,
          stack: error.stack,
        });
        if (error.message.includes('No recording in progress')) {
          return;
        }
      } else if (typeof error === 'string' && error.includes('No recording in progress')) {
        return;
      } else if (error && typeof error === 'object' && 'toString' in error) {
        if (error.toString().includes('No recording in progress')) {
          return;
        }
      }
      setIsProcessing(false);
      onRecordingStop(false);
    } finally {
      setIsStopping(false);
    }
  }, [onRecordingStop]);

  const handleStopRecording = useCallback(async () => {
    console.log('handleStopRecording called - isRecording:', isRecording, 'isStarting:', isStarting, 'isStopping:', isStopping);
    if (!isRecording || isStarting || isStopping) {
      console.log('Early return from handleStopRecording due to state check');
      return;
    }

    console.log('Stopping recording...');

    // Notify parent immediately (for UI state updates)
    onStopInitiated?.();

    setIsStopping(true);

    // Immediately trigger the stop action
    await stopRecordingAction();
  }, [isRecording, isStarting, isStopping, stopRecordingAction, onStopInitiated]);

  const handlePauseRecording = useCallback(async () => {
    if (!isRecording || isPaused || isPausing) return;

    console.log('Pausing recording...');
    setIsPausing(true);

    try {
      await invoke('pause_recording');
      // isPaused state now managed by RecordingStateContext via events
      console.log('Recording paused successfully');
    } catch (error) {
      console.error('Failed to pause recording:', error);
      alert('Failed to pause recording. Please check the console for details.');
    } finally {
      setIsPausing(false);
    }
  }, [isRecording, isPaused, isPausing]);

  const handleResumeRecording = useCallback(async () => {
    if (!isRecording || !isPaused || isResuming) return;

    console.log('Resuming recording...');
    setIsResuming(true);

    try {
      await invoke('resume_recording');
      // isPaused state now managed by RecordingStateContext via events
      console.log('Recording resumed successfully');
    } catch (error) {
      console.error('Failed to resume recording:', error);
      alert('Failed to resume recording. Please check the console for details.');
    } finally {
      setIsResuming(false);
    }
  }, [isRecording, isPaused, isResuming]);

  useEffect(() => {
    return () => {
      // Cleanup on unmount if needed
    };
  }, []);

  useEffect(() => {
    console.log('Setting up recording event listeners');
    let unsubscribes: (() => void)[] = [];

    const setupListeners = async () => {
      try {
        // Transcript error listener - handles both regular and actionable errors
        const transcriptErrorUnsubscribe = await listen('transcript-error', (event) => {
          console.log('transcript-error event received:', event);
          console.error('Transcription error received:', event.payload);
          const errorMessage = event.payload as string;

          Analytics.trackTranscriptionError(errorMessage);
          console.log('Tracked transcription error:', errorMessage);

          setTranscriptionErrors(prev => {
            const newCount = prev + 1;
            console.log('Transcription error count incremented:', newCount);
            return newCount;
          });
          setIsProcessing(false);
          console.log('Calling onRecordingStop(false) due to transcript error');
          onRecordingStop(false);
          if (onTranscriptionError) {
            onTranscriptionError(errorMessage);
          }
        });

        // Transcription error listener - handles structured error objects with actionable flag
        const transcriptionErrorUnsubscribe = await listen('transcription-error', (event) => {
          console.log('transcription-error event received:', event);
          console.error('Transcription error received:', event.payload);

          let errorMessage: string;
          let isActionable = false;

          if (typeof event.payload === 'object' && event.payload !== null) {
            const payload = event.payload as { error: string, userMessage: string, actionable: boolean };
            errorMessage = payload.userMessage || payload.error;
            isActionable = payload.actionable || false;
          } else {
            errorMessage = String(event.payload);
          }

          Analytics.trackTranscriptionError(errorMessage);
          console.log('Tracked transcription error:', errorMessage);

          setTranscriptionErrors(prev => {
            const newCount = prev + 1;
            console.log('Transcription error count incremented:', newCount);
            return newCount;
          });
          setIsProcessing(false);
          console.log('Calling onRecordingStop(false) due to transcription error');
          onRecordingStop(false);

          // For actionable errors (like model loading failures), the main page will handle showing the model selector
          // For regular errors, they are handled by useModalState global listener which shows a toast
          // We don't want to show a modal (via onTranscriptionError) AND a toast, so we skip the callback here
          /* if (onTranscriptionError && !isActionable) {
            onTranscriptionError(errorMessage);
          } */
        });

        // Pause/Resume events are now handled by RecordingStateContext
        // No need for duplicate listeners here

        // Speech detected listener - for UX feedback when VAD detects speech
        const speechDetectedUnsubscribe = await listen('speech-detected', (event) => {
          console.log('speech-detected event received:', event);
          setSpeechDetected(true);
        });

        unsubscribes = [
          transcriptErrorUnsubscribe,
          transcriptionErrorUnsubscribe,
          speechDetectedUnsubscribe
        ];
        console.log('Recording event listeners set up successfully');
      } catch (error) {
        console.error('Failed to set up recording event listeners:', error);
      }
    };

    setupListeners();

    return () => {
      console.log('Cleaning up recording event listeners');
      unsubscribes.forEach(unsubscribe => {
        if (unsubscribe && typeof unsubscribe === 'function') {
          unsubscribe();
        }
      });
    };
  }, [onRecordingStop, onTranscriptionError]);

  return (
    <TooltipProvider>
      <div className="flex flex-col space-y-2">
        <div className={`flex items-center gap-1 rounded-full ${isRecording ? 'bg-card p-1.5 shadow-lg' : ''}`}>
          {isProcessing && !isParentProcessing ? (
            <StatusMessage message="Processing recording…" />
          ) : (
            <>
              {showPlayback ? (
                <>
                  <button
                    onClick={handleStartRecording}
                    className="w-10 h-10 flex items-center justify-center bg-destructive rounded-full text-destructive-foreground hover:bg-destructive/90 transition-colors"
                  >
                    <Mic size={16} />
                  </button>

                  <div className="w-px h-6 bg-accent mx-1" />

                  <div className="flex items-center space-x-1 mx-2">
                    <div className="text-sm text-muted-foreground min-w-[40px]">
                      {formatTime(currentTime)}
                    </div>
                    <Progress value={progress} className="w-24 h-1" />
                    <div className="text-sm text-muted-foreground min-w-[40px]">
                      {formatTime(duration)}
                    </div>
                  </div>

                  <button
                    className="w-10 h-10 flex items-center justify-center bg-muted-foreground/30 rounded-full text-background cursor-not-allowed"
                    disabled
                  >
                    <Play size={16} />
                  </button>
                </>
              ) : (
                <>
                  {!isRecording ? (
                    // The home screen's one primary action, labelled so it never reads as a bare icon.
                    <button
                      onClick={() => {
                        Analytics.trackButtonClick('start_recording', 'recording_controls');
                        handleStartRecording();
                      }}
                      disabled={isStarting || isProcessing || isRecordingDisabled || isValidatingModel}
                      className="flex h-11 items-center gap-2 rounded-full bg-destructive px-5 text-sm font-medium text-destructive-foreground transition-colors hover:bg-destructive/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:bg-muted-foreground/40"
                    >
                      {isValidatingModel || isStarting ? (
                        <Spinner className="h-4 w-4 text-destructive-foreground" />
                      ) : (
                        <Mic size={16} />
                      )}
                      {isValidatingModel ? 'Checking Model…' : isStarting ? 'Starting…' : 'Start Recording'}
                    </button>
                  ) : (
                    <>
                      <div className="flex items-center gap-2 pl-1 pr-2">
                        <span
                          aria-hidden
                          className={`h-2 w-2 rounded-full ${isPaused ? 'bg-warning' : 'bg-destructive motion-safe:animate-pulse'}`}
                        />
                        <span className="text-sm text-foreground" aria-live="polite">
                          {statusLabel}
                        </span>
                        <span className="text-sm text-muted-foreground tabular-nums">
                          {formatElapsed(recordingState.activeDuration ?? 0)}
                        </span>
                      </div>

                      {/* Real microphone levels, so a silent mic shows as silent. */}
                      <div className="flex h-6 items-center gap-1 px-2" aria-hidden>
                        {micLevels.map((level, index) => (
                          <div
                            key={index}
                            className={`w-1 rounded-full transition-[height] duration-150 ${isPaused ? 'bg-warning/60' : 'bg-destructive'}`}
                            style={{ height: isPaused ? 4 : 4 + level * 20 }}
                          />
                        ))}
                      </div>

                      <button
                        onClick={() => {
                          if (isPaused) {
                            Analytics.trackButtonClick('resume_recording', 'recording_controls');
                            handleResumeRecording();
                          } else {
                            Analytics.trackButtonClick('pause_recording', 'recording_controls');
                            handlePauseRecording();
                          }
                        }}
                        disabled={isPausing || isResuming || isStopping}
                        aria-label={isPaused ? 'Resume Recording' : 'Pause Recording'}
                        title={isPaused ? 'Resume Recording' : 'Pause Recording'}
                        className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-border bg-card text-muted-foreground transition-colors hover:border-foreground/30 hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:bg-accent"
                      >
                        {isPaused ? <Play size={16} /> : <Pause size={16} />}
                      </button>

                      <button
                        onClick={() => {
                          Analytics.trackButtonClick('stop_recording', 'recording_controls');
                          handleStopRecording();
                        }}
                        disabled={isStopping || isPausing || isResuming}
                        aria-label="Stop Recording"
                        title="Stop Recording"
                        className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive text-destructive-foreground transition-colors hover:bg-destructive/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:bg-muted-foreground/40"
                      >
                        <Square size={16} />
                      </button>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* Show validation status only */}
        {isValidatingModel && (
          <div className="text-xs text-muted-foreground text-center mt-2">
            Checking the speech recognition model…
          </div>
        )}

        {/* Device error alert */}
        {deviceError && (
          <Alert variant="destructive" className="mt-4 border-destructive/40 bg-destructive/10">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <button
              onClick={() => setDeviceError(null)}
              className="absolute right-3 top-3 text-destructive hover:text-destructive transition-colors"
              aria-label="Close alert"
            >
              <X className="h-4 w-4" />
            </button>
            <AlertTitle className="text-destructive font-semibold mb-2">
              {deviceError.title}
            </AlertTitle>
            <AlertDescription className="text-destructive">
              {deviceError.message.split('\n').map((line, i) => (
                <div key={i} className={i > 0 ? 'ml-2' : ''}>
                  {line}
                </div>
              ))}
            </AlertDescription>
          </Alert>
        )}

        {/* {showPlayback && recordingPath && (
        <div className="text-sm text-muted-foreground px-4">
          Recording saved to: {recordingPath}
        </div>
      )} */}
      </div>
    </TooltipProvider>
  );
};
