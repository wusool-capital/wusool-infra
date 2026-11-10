import { PreferenceSettings } from "@/components/PreferenceSettings";
import { DeviceSelection } from "@/components/DeviceSelection";
import { LanguageSelection } from "@/components/LanguageSelection";
import { TranscriptSettings } from "@/components/TranscriptSettings";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { useConfig } from "@/contexts/ConfigContext";
import { useRecordingState } from "@/contexts/RecordingStateContext";
import { ScrollArea } from "@/components/ui/scroll-area";

type modalType = "modelSettings" | "deviceSettings" | "languageSettings" | "modelSelector" | "errorAlert" | "chunkDropWarning";

/**
 * SettingsModals Component
 *
 * All settings modals consolidated into a single component.
 * Uses ConfigContext and RecordingStateContext internally - no prop drilling needed!
 */

interface SettingsModalsProps {
  modals: {
    modelSettings: boolean;
    deviceSettings: boolean;
    languageSettings: boolean;
    modelSelector: boolean;
    errorAlert: boolean;
    chunkDropWarning: boolean;
  };
  messages: {
    errorAlert: string;
    chunkDropWarning: string;
    modelSelector: string;
  };
  onClose: (name: modalType) => void;
}

export function SettingsModals({
  modals,
  messages,
  onClose,
}: SettingsModalsProps) {
  // Contexts
  const {
    selectedDevices,
    setSelectedDevices,
    selectedLanguage,
    setSelectedLanguage,
    transcriptModelConfig,
    setTranscriptModelConfig,
    showConfidenceIndicator,
    toggleConfidenceIndicator,
  } = useConfig();

  const { isRecording } = useRecordingState();

  return <>
    {/* Legacy Settings Modal */}
    <Dialog open={modals.modelSettings} onOpenChange={(open) => !open && onClose("modelSettings")}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col p-0">
        <DialogHeader className="p-6 pb-4 border-b border-border">
          <DialogTitle>Preferences</DialogTitle>
        </DialogHeader>

        {/* Content - Scrollable */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="p-6 space-y-8">
          {/* General Preferences Section */}
          <PreferenceSettings />
          </div>
        </ScrollArea>

        <DialogFooter className="p-6 pt-4 border-t border-border">
          <Button onClick={() => onClose('modelSettings')}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    {/* Device Settings Modal */}
    <Dialog open={modals.deviceSettings} onOpenChange={(open) => !open && onClose('deviceSettings')}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Audio Device Settings</DialogTitle>
        </DialogHeader>

        <DeviceSelection
          selectedDevices={selectedDevices}
          onDeviceChange={setSelectedDevices}
          disabled={isRecording}
        />

        <DialogFooter>
          <Button
            onClick={() => {
              const micDevice = selectedDevices.micDevice || 'Default';
              const systemDevice = selectedDevices.systemDevice || 'Default';
              toast.success("Devices selected", {
                description: `Microphone: ${micDevice}, System Audio: ${systemDevice}`
              });
              onClose('deviceSettings');
            }}
          >
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    {/* Language Settings Modal */}
    <Dialog open={modals.languageSettings} onOpenChange={(open) => !open && onClose('languageSettings')}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Language Settings</DialogTitle>
        </DialogHeader>

        <LanguageSelection
          selectedLanguage={selectedLanguage}
          onLanguageChange={setSelectedLanguage}
          disabled={isRecording}
          provider={transcriptModelConfig.provider}
        />

        <DialogFooter>
          <Button onClick={() => onClose('languageSettings')}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    {/* Model Selection Modal */}
    <Dialog open={modals.modelSelector} onOpenChange={(open) => !open && onClose('modelSelector')}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col p-0">
        <DialogHeader className="p-6 pb-4 border-b border-border">
          <DialogTitle>
            {messages.modelSelector ? 'Speech Recognition Setup Required' : 'Transcription Model Settings'}
          </DialogTitle>
        </DialogHeader>

        {/* Scrollable Content */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="p-6 pt-4">
            <TranscriptSettings
              transcriptModelConfig={transcriptModelConfig}
              setTranscriptModelConfig={setTranscriptModelConfig}
              onModelSelect={() => onClose('modelSelector')}
            />
          </div>
        </ScrollArea>

        {/* Fixed Footer */}
        <DialogFooter className="p-6 pt-4 border-t border-border sm:justify-between">
          {/* Confidence Indicator Toggle */}
          <div className="flex items-center gap-3">
            <Switch
              checked={showConfidenceIndicator}
              onCheckedChange={toggleConfidenceIndicator}
            />
            <div>
              <p className="text-sm font-medium text-foreground">Show Confidence Indicators</p>
              <p className="text-xs text-muted-foreground">Display colored dots showing transcription confidence quality</p>
            </div>
          </div>

          <Button variant="secondary" onClick={() => onClose('modelSelector')}>
            {messages.modelSelector ? 'Cancel' : 'Done'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    {/* Error Alert Modal */}
    {modals.errorAlert && (
      <div className="fixed inset-0 bg-foreground/40 flex items-center justify-center z-50">
        <Alert variant="destructive" className="max-w-md mx-4 bg-card shadow-xl">
          <AlertTitle>Recording Stopped</AlertTitle>
          <AlertDescription>
            {messages.errorAlert}
            <Button
              variant="link"
              className="ml-2 h-auto p-0 text-destructive"
              onClick={() => onClose('errorAlert')}
            >
              Dismiss
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )}

    {/* Chunk Drop Warning Modal */}
    {modals.chunkDropWarning && (
      <div className="fixed inset-0 bg-foreground/40 flex items-center justify-center z-50">
        <Alert variant="warning" className="max-w-lg mx-4 bg-card shadow-xl">
          <AlertTitle>Transcription Performance Warning</AlertTitle>
          <AlertDescription>
            {messages.chunkDropWarning}
            <Button
              variant="link"
              className="ml-2 h-auto p-0 text-warning"
              onClick={() => onClose('chunkDropWarning')}
            >
              Dismiss
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )}
  </>
}
