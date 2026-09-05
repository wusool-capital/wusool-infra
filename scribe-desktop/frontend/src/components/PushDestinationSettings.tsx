import React, { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { Send } from 'lucide-react';

interface PushConfig {
  server_url: string;
  api_key: string;
  install_id: string;
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

  useEffect(() => {
    const load = async () => {
      try {
        const config = await invoke<PushConfig>('get_push_config');
        setServerUrl(config.server_url);
        setApiKey(config.api_key);
        setInstallId(config.install_id);
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
      const config = await invoke<PushConfig>('set_push_config', {
        serverUrl: serverUrl.trim(),
        apiKey: apiKey.trim(),
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

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">Push Destination</h3>
        <p className="text-sm text-muted-foreground mb-6">
          Where a pushed meeting is sent for server-side summarization. Summaries are
          generated remotely, delivered to Slack, and sent back here.
        </p>
      </div>

      <div className="space-y-4 p-4 border rounded-lg">
        <div>
          <label htmlFor="server-url" className="block text-sm font-medium text-foreground/90 mb-1">
            Server URL
          </label>
          <Input
            id="server-url"
            placeholder="https://scribe.example.com"
            value={serverUrl}
            onChange={(e) => setServerUrl(e.target.value)}
            disabled={saving}
          />
        </div>

        <div>
          <label htmlFor="api-key" className="block text-sm font-medium text-foreground/90 mb-1">
            API Key
          </label>
          <Input
            id="api-key"
            type="password"
            placeholder="Shared desktop API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={saving}
          />
          <p className="text-xs text-muted-foreground mt-1">
            Sent as <code>Authorization: Bearer &lt;key&gt;</code> on every push.
          </p>
        </div>

        <Button onClick={handleSave} disabled={saving} size="sm">
          <Send className="w-4 h-4 mr-1" />
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>

      <div className="p-4 border rounded-lg bg-muted">
        <div className="text-sm font-medium text-foreground/90 mb-1">Install ID</div>
        <div className="text-xs text-muted-foreground break-all">{installId}</div>
        <p className="text-xs text-muted-foreground mt-1">
          Generated automatically; identifies this install to the backend.
        </p>
      </div>
    </div>
  );
}
