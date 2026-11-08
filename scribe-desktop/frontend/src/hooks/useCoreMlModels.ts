import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

export type DiarizationBackend = 'cpu' | 'coreml';

// Mirror the Rust `DiarizationBackendSettings`, `DiarizationModelsStatus` and `DownloadProgress` payloads.
export interface DiarizationBackendSettings {
  backend: DiarizationBackend;
  /** False off macOS, where the CoreML option is hidden. */
  coreml_available: boolean;
}
export interface DiarizationModelsStatus {
  cpu_ready: boolean;
  coreml_ready: boolean;
}
export interface DownloadProgress {
  downloaded: number;
  total: number;
}

export type CoreMlDownloadState =
  | { stage: 'closed' }
  | { stage: 'confirm' }
  | { stage: 'downloading' }
  | { stage: 'failed'; error: string };

export interface CoreMlModels {
  settings: DiarizationBackendSettings | null;
  models: DiarizationModelsStatus | null;
  /** CoreML is chosen but its models aren't on disk yet, so separation would run on CPU. */
  needsDownload: boolean;
  download: CoreMlDownloadState;
  progress: DownloadProgress;
  setBackend: (backend: DiarizationBackend) => Promise<void>;
  refresh: () => Promise<void>;
  /** Opens the download prompt. */
  ask: () => void;
  /** Downloads the CoreML models; resolves true once they're ready. */
  start: () => Promise<boolean>;
  /** Cancels a running download, or closes the prompt. */
  close: () => void;
}

/** Shared by Settings and the Separate Speakers prompt, so both download the same way. */
export function useCoreMlModels(enabled = true): CoreMlModels {
  const [settings, setSettings] = useState<DiarizationBackendSettings | null>(null);
  const [models, setModels] = useState<DiarizationModelsStatus | null>(null);
  const [download, setDownload] = useState<CoreMlDownloadState>({ stage: 'closed' });
  const [progress, setProgress] = useState<DownloadProgress>({ downloaded: 0, total: 0 });

  const refresh = useCallback(async () => {
    const [nextSettings, nextModels] = await Promise.all([
      invoke<DiarizationBackendSettings>('get_diarization_backend'),
      invoke<DiarizationModelsStatus>('get_diarization_models_status'),
    ]);
    setSettings(nextSettings);
    setModels(nextModels);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    refresh().catch(() => undefined);
    const unlisten = listen<DownloadProgress>('diarization-models-progress', (event) => setProgress(event.payload));
    return () => {
      unlisten.then((stop) => stop());
    };
  }, [enabled, refresh]);

  const setBackend = useCallback(async (backend: DiarizationBackend) => {
    await invoke('set_diarization_backend', { backend });
    setSettings((current) => (current ? { ...current, backend } : current));
  }, []);

  const start = useCallback(async () => {
    setProgress({ downloaded: 0, total: 0 });
    setDownload({ stage: 'downloading' });
    try {
      await invoke('download_diarization_models', { backend: 'coreml' });
      await refresh();
      setDownload({ stage: 'closed' });
      return true;
    } catch (error) {
      const message = String(error);
      setDownload(message.includes('cancelled') ? { stage: 'closed' } : { stage: 'failed', error: message });
      await refresh().catch(() => undefined);
      return false;
    }
  }, [refresh]);

  const close = useCallback(() => {
    if (download.stage === 'downloading') void invoke('cancel_diarization_model_download');
    else setDownload({ stage: 'closed' });
  }, [download.stage]);

  return {
    settings,
    models,
    needsDownload: Boolean(settings?.coreml_available && settings.backend === 'coreml' && models && !models.coreml_ready),
    download,
    progress,
    setBackend,
    refresh,
    ask: () => setDownload({ stage: 'confirm' }),
    start,
    close,
  };
}
