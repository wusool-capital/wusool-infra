import React, { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { SettingsRow, SettingsSection } from '@/components/settings/SettingsSection';

interface PushConfig {
  server_url: string;
  api_key: string;
  install_id: string;
  skip_attio: boolean;
}

/**
 * Where "Push" (see MeetingDetails/PushMeetingButton.tsx) sends a
 * finished transcript for server-side summarization -- the Scribe
 * backend's base URL and the shared API key it authenticates with
 * (Authorization: Bearer <api_key>, checked against Scribe's
 * DESKTOP_API_KEY setting).
 */
export function PushDestinationSettings() {
  const [serverUrl, setServerUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [installId, setInstallId] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [skipAttio, setSkipAttio] = useState(false);
  const [pendingSkipAttio, setPendingSkipAttio] = useState<boolean | null>(null);
  const [password, setPassword] = useState('');
  const [unlocking, setUnlocking] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const config = await invoke<PushConfig>('get_push_config');
        setServerUrl(config.server_url);
        setApiKey(config.api_key);
        setInstallId(config.install_id);
        setSkipAttio(config.skip_attio);
      } catch (error) {
        console.error('Failed to load push config:', error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const trimmedUrl = serverUrl.trim();
      const trimmedKey = apiKey.trim();
      await invoke('verify_push_config', { serverUrl: trimmedUrl, apiKey: trimmedKey });

      const config = await invoke<PushConfig>('set_push_config', {
        serverUrl: trimmedUrl,
        apiKey: trimmedKey,
      });
      setServerUrl(config.server_url);
      setApiKey(config.api_key);
      toast.success('Push destination saved');
    } catch (error) {
      console.error('Failed to save push config:', error);
      toast.error('Failed to save push destination', {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setSaving(false);
    }
  };

  const closeSkipAttioDialog = () => {
    setPendingSkipAttio(null);
    setPassword('');
  };

  const handleSkipAttioConfirm = async () => {
    if (pendingSkipAttio === null) return;
    setUnlocking(true);
    try {
      const config = await invoke<PushConfig>('set_skip_attio', {
        enabled: pendingSkipAttio,
        password,
      });
      setSkipAttio(config.skip_attio);
      toast.success(config.skip_attio ? 'Attio writes disabled' : 'Attio writes enabled');
      closeSkipAttioDialog();
    } catch (error) {
      toast.error('Could not change setting', {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setUnlocking(false);
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
      <SettingsSection
        title="Scribe Push"
        description="Where a pushed meeting is sent to be summarized. The summary comes back to this app."
      >
        <SettingsRow title="Server URL" htmlFor="server-url">
          <Input
            id="server-url"
            name="server-url"
            type="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="Server address from your admin"
            value={serverUrl}
            onChange={(e) => setServerUrl(e.target.value)}
            disabled={saving}
          />
        </SettingsRow>
        <SettingsRow title="API Key" htmlFor="api-key" description="Ask your Scribe admin for this key.">
          <Input
            id="api-key"
            name="api-key"
            type="password"
            autoComplete="off"
            placeholder="Shared desktop API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={saving}
          />
        </SettingsRow>
        <div className="flex justify-end px-5 py-3">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving ? 'Verifying…' : 'Save'}
          </Button>
        </div>
      </SettingsSection>

      <details className="group">
        <summary className="cursor-pointer select-none text-sm font-medium text-muted-foreground hover:text-foreground">
          Developer Options
        </summary>
        <div className="mt-3 divide-y divide-border rounded-lg border border-border bg-card">
          <SettingsRow
            title="Don't Store to Attio"
            description="Pushed meetings are still summarized, but no Attio note is created. Needs the developer password to change."
            control={
              <Switch
                aria-label="Don't store to Attio"
                checked={skipAttio}
                onCheckedChange={(checked) => setPendingSkipAttio(checked)}
              />
            }
          />
          <SettingsRow
            title="Install ID"
            description={
              <>
                <span className="break-all text-foreground">{installId}</span>
                <span className="block">Generated automatically; identifies this install to the server.</span>
              </>
            }
          />
        </div>
      </details>

      <Dialog open={pendingSkipAttio !== null} onOpenChange={(open) => !open && closeSkipAttioDialog()}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Developer password</DialogTitle>
            <DialogDescription>
              Enter the developer password to {pendingSkipAttio ? 'stop' : 'resume'} storing pushed
              meetings in Attio.
            </DialogDescription>
          </DialogHeader>
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSkipAttioConfirm()}
            disabled={unlocking}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={closeSkipAttioDialog} disabled={unlocking}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSkipAttioConfirm} disabled={unlocking || !password}>
              {unlocking ? 'Checking...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
