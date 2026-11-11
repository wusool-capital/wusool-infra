import React, { useState, useEffect } from 'react';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { FolderOpen } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { DeviceSelection, SelectedDevices } from '@/components/DeviceSelection';
import Analytics from '@/lib/analytics';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { SettingsRow, SettingsSection } from '@/components/settings/SettingsSection';
import { useConfig } from '@/contexts/ConfigContext';

export interface RecordingPreferences {
  save_folder: string;
  auto_save: boolean;
  file_format: string;
  preferred_mic_device: string | null;
  preferred_system_device: string | null;
  auto_stop_on_meeting_end: boolean;
}

interface RecordingSettingsProps {
  onSave?: (preferences: RecordingPreferences) => void;
}

export function RecordingSettings({ onSave }: RecordingSettingsProps) {
  const { setSelectedDevices } = useConfig();
  const [preferences, setPreferences] = useState<RecordingPreferences>({
    save_folder: '',
    auto_save: true,
    file_format: 'mp4',
    preferred_mic_device: null,
    preferred_system_device: null,
    auto_stop_on_meeting_end: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showRecordingNotification, setShowRecordingNotification] = useState(true);
  // null until the OS login-item state is read, since it's the source of truth.
  const [openAtLogin, setOpenAtLogin] = useState<boolean | null>(null);

  // Load recording preferences on component mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const prefs = await invoke<RecordingPreferences>('get_recording_preferences');
        setPreferences(prefs);
      } catch (error) {
        console.error('Failed to load recording preferences:', error);
        // If loading fails, get default folder path
        try {
          const defaultPath = await invoke<string>('get_default_recordings_folder_path');
          setPreferences(prev => ({ ...prev, save_folder: defaultPath }));
        } catch (defaultError) {
          console.error('Failed to get default folder path:', defaultError);
        }
      } finally {
        setLoading(false);
      }
    };

    loadPreferences();
  }, []);

  useEffect(() => {
    invoke<boolean>('get_open_at_login')
      .then(setOpenAtLogin)
      .catch((error) => {
        console.error('Failed to read open-at-login state:', error);
        // Leave the toggle usable so it can still be turned on or off.
        setOpenAtLogin(false);
      });
  }, []);

  // Load recording notification preference
  useEffect(() => {
    const loadNotificationPref = async () => {
      try {
        const { Store } = await import('@tauri-apps/plugin-store');
        const store = await Store.load('preferences.json');
        const show = await store.get<boolean>('show_recording_notification') ?? true;
        setShowRecordingNotification(show);
      } catch (error) {
        console.error('Failed to load notification preference:', error);
      }
    };
    loadNotificationPref();
  }, []);

  const handleAutoSaveToggle = async (enabled: boolean) => {
    const newPreferences = { ...preferences, auto_save: enabled };
    setPreferences(newPreferences);
    await savePreferences(newPreferences);

    // Track auto-save setting change
    await Analytics.track('auto_save_recording_toggled', {
      enabled: enabled.toString()
    });
  };

  const handleDeviceChange = async (devices: SelectedDevices) => {
    const newPreferences = {
      ...preferences,
      preferred_mic_device: devices.micDevice,
      preferred_system_device: devices.systemDevice
    };
    setPreferences(newPreferences);
    await savePreferences(newPreferences);

    // Track default device preference changes
    // Note: Individual device selection analytics are tracked in DeviceSelection component
    await Analytics.track('default_devices_changed', {
      has_preferred_microphone: (!!devices.micDevice).toString(),
      has_preferred_system_audio: (!!devices.systemDevice).toString()
    });
  };

  const handleOpenFolder = async () => {
    try {
      await invoke('open_recordings_folder');
    } catch (error) {
      console.error('Failed to open recordings folder:', error);
    }
  };

  const handleNotificationToggle = async (enabled: boolean) => {
    try {
      setShowRecordingNotification(enabled);
      const { Store } = await import('@tauri-apps/plugin-store');
      const store = await Store.load('preferences.json');
      await store.set('show_recording_notification', enabled);
      await store.save();
      toast.success('Preference saved');
      await Analytics.track('recording_notification_preference_changed', {
        enabled: enabled.toString()
      });
    } catch (error) {
      console.error('Failed to save notification preference:', error);
      toast.error('Failed to save preference');
    }
  };

  const handleOpenAtLoginToggle = async (enabled: boolean) => {
    const previous = openAtLogin;
    setOpenAtLogin(enabled);
    try {
      await invoke('set_open_at_login', { enabled });
      toast.success('Preference saved');
      await Analytics.track('open_at_login_changed', {
        enabled: enabled.toString()
      });
    } catch (error) {
      console.error('Failed to save open-at-login preference:', error);
      setOpenAtLogin(previous);
      toast.error('Failed to save preference');
    }
  };

  const handleAutoStopToggle = async (enabled: boolean) => {
    const updated = { ...preferences, auto_stop_on_meeting_end: enabled };
    setPreferences(updated);
    try {
      await invoke('set_recording_preferences', { preferences: updated });
      toast.success('Preference saved');
      await Analytics.track('auto_stop_on_meeting_end_changed', {
        enabled: enabled.toString()
      });
    } catch (error) {
      console.error('Failed to save auto-stop preference:', error);
      setPreferences(preferences);
      toast.error('Failed to save preference');
    }
  };

  const savePreferences = async (prefs: RecordingPreferences) => {
    setSaving(true);
    try {
      await invoke('set_recording_preferences', { preferences: prefs });
      onSave?.(prefs);
      // The app-wide selection drives the home screen and the next recording, so it follows the saved choice.
      setSelectedDevices({ micDevice: prefs.preferred_mic_device, systemDevice: prefs.preferred_system_device });

      // Show success toast with device details
      const micDevice = prefs.preferred_mic_device || 'Default';
      const systemDevice = prefs.preferred_system_device || 'Default';
      toast.success("Device preferences saved", {
        description: `Microphone: ${micDevice}, System Audio: ${systemDevice}`
      });
    } catch (error) {
      console.error('Failed to save recording preferences:', error);
      toast.error("Failed to save device preferences", {
        description: error instanceof Error ? error.message : String(error)
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <SettingsSection title="Recordings" description="How meetings are recorded and saved on this Mac.">
        <SettingsRow
          title="Save Audio Recordings"
          description={
            preferences.auto_save
              ? "Keep each meeting's audio. Needed to separate speakers and to re-transcribe later."
              : "Off: only the transcript is kept, and speakers are not separated."
          }
          control={
            <Switch
              aria-label="Save audio recordings"
              checked={preferences.auto_save}
              onCheckedChange={handleAutoSaveToggle}
              disabled={saving}
            />
          }
        />

        {preferences.auto_save && (
          <SettingsRow
            title="Save Location"
            description={
              <>
                <span className="break-all">{preferences.save_folder || 'Default folder'}</span>
                <span className="block">Each meeting is saved in its own folder.</span>
              </>
            }
            control={
              <Button variant="outline" size="sm" onClick={handleOpenFolder}>
                <FolderOpen className="w-4 h-4" />
                Open Folder
              </Button>
            }
          />
        )}

        <SettingsRow
          title="Recording Start Notification"
          description="Show a reminder to tell participants that the meeting is being recorded."
          control={
            <Switch
              aria-label="Recording start notification"
              checked={showRecordingNotification}
              onCheckedChange={handleNotificationToggle}
            />
          }
        />

        <SettingsRow
          title="Auto-stop When Meeting Ends"
          description="Stop recording after a short countdown when your meeting app releases the microphone. When off, recording continues until you stop it from the tray menu or the app."
          control={
            <Switch
              aria-label="Auto-stop when meeting ends"
              checked={preferences.auto_stop_on_meeting_end}
              onCheckedChange={handleAutoStopToggle}
            />
          }
        />

        <SettingsRow
          title="Open at Login"
          description="Start Scribe in the background when you log in, so it is already running for your meetings. Find it in the menu bar."
          control={
            <Switch
              aria-label="Open at login"
              checked={openAtLogin ?? false}
              disabled={openAtLogin === null}
              onCheckedChange={handleOpenAtLoginToggle}
            />
          }
        />
      </SettingsSection>

      <SettingsSection
        title="Default Audio Devices"
        description="Selected automatically when a new recording starts."
      >
        <div className="px-5 py-4">
          <DeviceSelection
            selectedDevices={{
              micDevice: preferences.preferred_mic_device,
              systemDevice: preferences.preferred_system_device
            }}
            onDeviceChange={handleDeviceChange}
            disabled={saving}
          />
        </div>
      </SettingsSection>
    </div>
  );
}
