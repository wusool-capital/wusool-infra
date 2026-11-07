"use client"

import { useEffect, useState } from "react"
import { invoke } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import { Trash2 } from "lucide-react"
import type { SpeakerProfileSummary } from "@/lib/speakers"
import { Input } from "./ui/input"
import { Button } from "./ui/button"
import { Switch } from "./ui/switch"
import { ConfirmationModal } from "./ConfirmationModel/confirmation-modal"
import { SettingsRow, SettingsSection } from "./settings/SettingsSection"
import { Progress } from "./ui/progress"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog"

type DiarizationBackend = "cpu" | "coreml"

// Mirrors the Rust `DiarizationBackendSettings` serialization.
interface DiarizationBackendSettings {
  backend: DiarizationBackend
  coreml_available: boolean
}

// Mirror the Rust `DiarizationModelsStatus` and `DownloadProgress` payloads.
interface DiarizationModelsStatus {
  cpu_ready: boolean
  coreml_ready: boolean
}
interface DownloadProgress {
  downloaded: number
  total: number
}

type DownloadState =
  | { stage: "closed" }
  | { stage: "confirm" }
  | { stage: "downloading" }
  | { stage: "failed"; error: string }

const megabytes = (bytes: number) => Math.round(bytes / 1_000_000)

export function SpeakerSettings() {
  const [selfName, setSelfName] = useState("")
  const [savedSelfName, setSavedSelfName] = useState("")
  const [justSaved, setJustSaved] = useState(false)
  const [profiles, setProfiles] = useState<SpeakerProfileSummary[]>([])
  const [pendingDelete, setPendingDelete] = useState<SpeakerProfileSummary | null>(null)
  const [backend, setBackend] = useState<DiarizationBackendSettings | null>(null)
  const [models, setModels] = useState<DiarizationModelsStatus | null>(null)
  const [download, setDownload] = useState<DownloadState>({ stage: "closed" })
  const [progress, setProgress] = useState<DownloadProgress>({ downloaded: 0, total: 0 })
  const [confirmingOff, setConfirmingOff] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadProfiles = async () => setProfiles(await invoke<SpeakerProfileSummary[]>("list_speaker_profiles"))

  useEffect(() => {
    ;(async () => {
      try {
        const name = (await invoke<string | null>("get_self_speaker_name")) ?? ""
        setSelfName(name)
        setSavedSelfName(name)
        await loadProfiles()
        setBackend(await invoke<DiarizationBackendSettings>("get_diarization_backend"))
        setModels(await invoke<DiarizationModelsStatus>("get_diarization_models_status"))
      } catch (e) {
        setError(String(e))
      }
    })()
  }, [])

  const saveSelfName = async () => {
    const name = selfName.trim()
    if (name === savedSelfName) return
    try {
      await invoke("set_self_speaker_name", { name: name || null })
      setSavedSelfName(name)
      setJustSaved(true)
      setTimeout(() => setJustSaved(false), 2000)
      setError(null)
    } catch (e) {
      setError(String(e))
    }
  }

  useEffect(() => {
    const unlisten = listen<DownloadProgress>("diarization-models-progress", (event) => setProgress(event.payload))
    return () => {
      unlisten.then((stop) => stop())
    }
  }, [])

  const saveBackend = async (next: DiarizationBackend) => {
    await invoke("set_diarization_backend", { backend: next })
    setBackend((current) => (current ? { ...current, backend: next } : current))
  }

  const refreshModels = async () => setModels(await invoke<DiarizationModelsStatus>("get_diarization_models_status"))

  const toggleCoreMl = async (enabled: boolean) => {
    setError(null)
    if (!enabled) {
      setConfirmingOff(true)
      return
    }
    // Already downloaded (kept after turning off last time): switch straight on, no dialog.
    if (models?.coreml_ready) {
      await saveBackend("coreml").catch((e) => setError(String(e)))
      return
    }
    setDownload({ stage: "confirm" })
  }

  const startDownload = async () => {
    setProgress({ downloaded: 0, total: 0 })
    setDownload({ stage: "downloading" })
    try {
      await invoke("download_diarization_models", { backend: "coreml" })
      await saveBackend("coreml")
      await refreshModels()
      setDownload({ stage: "closed" })
    } catch (e) {
      const message = String(e)
      setDownload(message.includes("cancelled") ? { stage: "closed" } : { stage: "failed", error: message })
      await refreshModels().catch(() => undefined)
    }
  }

  const turnOff = async (deleteModels: boolean) => {
    setConfirmingOff(false)
    try {
      await saveBackend("cpu")
      if (deleteModels) await invoke("delete_coreml_models")
      await refreshModels()
    } catch (e) {
      setError(String(e))
    }
  }

  const confirmDelete = async () => {
    if (!pendingDelete) return
    try {
      await invoke("delete_speaker_profile", { profileId: pendingDelete.id })
      await loadProfiles()
    } catch (e) {
      setError(String(e))
    } finally {
      setPendingDelete(null)
    }
  }

  return (
    <SettingsSection
      title="Speakers"
      description="Scribe labels your microphone with your name and separates other voices after each meeting. Voice fingerprints stay on this device."
    >
      <SettingsRow
        title="Your Name"
        htmlFor="self-speaker-name"
        description={justSaved ? "Saved" : "Shown on everything you say in a transcript."}
      >
        <Input
          id="self-speaker-name"
          name="self-speaker-name"
          autoComplete="name"
          className="max-w-sm"
          value={selfName}
          onChange={(e) => setSelfName(e.target.value)}
          onBlur={saveSelfName}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          placeholder="Me"
        />
      </SettingsRow>

      {backend?.coreml_available && (
        <SettingsRow
          title="Faster Speaker Separation (CoreML)"
          description={
            models?.coreml_ready
              ? "About 6× faster. Uses up to 2.7 GB of memory while it runs. Models downloaded."
              : "About 6× faster. Uses up to 2.7 GB of memory while it runs, and downloads 260 MB once."
          }
          control={
            <Switch
              aria-label="Faster speaker separation"
              checked={backend.backend === "coreml"}
              onCheckedChange={toggleCoreMl}
            />
          }
        />
      )}

      <SettingsRow
        title="Recognised Voices"
        description={
          profiles.length === 0
            ? "None yet. Click a speaker's name in a meeting transcript to name them."
            : undefined
        }
      >
        {profiles.length > 0 && (
          <ul className="-mx-2">
            {profiles.map((profile) => (
              <li key={profile.id} className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted">
                <span className="min-w-0 truncate text-sm text-foreground">
                  {profile.name}
                  <span className="ml-2 text-muted-foreground tabular-nums">
                    {profile.sample_count} {profile.sample_count === 1 ? "meeting" : "meetings"}
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPendingDelete(profile)}
                  aria-label={`Forget ${profile.name}`}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </SettingsRow>

      {error && <p className="px-5 py-3 text-sm text-destructive">{error}</p>}

      <Dialog
        open={download.stage !== "closed"}
        onOpenChange={(open) => {
          // Closing mid-download would hide progress, so it cancels the download instead.
          if (open) return
          if (download.stage === "downloading") void invoke("cancel_diarization_model_download")
          else setDownload({ stage: "closed" })
        }}
      >
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>Download Faster Speaker Separation</DialogTitle>
            <DialogDescription>
              {download.stage === "failed"
                ? `The download didn't finish: ${download.error}`
                : "Scribe needs a one-time 260 MB download of CoreML voice models. Speaker separation keeps working on the standard model until it finishes."}
            </DialogDescription>
          </DialogHeader>
          {download.stage === "downloading" && (
            <div className="space-y-2">
              <Progress value={progress.total > 0 ? (progress.downloaded / progress.total) * 100 : 0} />
              <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
                {progress.total > 0
                  ? `${megabytes(progress.downloaded)} of ${megabytes(progress.total)} MB`
                  : "Preparing download…"}
              </p>
            </div>
          )}
          <DialogFooter>
            {download.stage === "downloading" ? (
              <Button variant="outline" onClick={() => void invoke("cancel_diarization_model_download")}>
                Cancel
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => setDownload({ stage: "closed" })}>
                  Not Now
                </Button>
                <Button onClick={() => void startDownload()}>
                  {download.stage === "failed" ? "Try Again" : "Download 260 MB"}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmingOff} onOpenChange={setConfirmingOff}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>Turn Off Faster Speaker Separation?</DialogTitle>
            <DialogDescription>
              Also delete the downloaded CoreML models (260 MB)? If you delete them, turning this back on means
              downloading them again. Keep them to switch back on instantly.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => void turnOff(false)}>
              Keep Models
            </Button>
            <Button variant="destructive" onClick={() => void turnOff(true)}>
              Delete Models
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmationModal
        isOpen={pendingDelete !== null}
        text={`Forget ${pendingDelete?.name ?? "this person"}'s voice? Past meetings keep their text but lose this name, and Scribe stops recognising them.`}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </SettingsSection>
  )
}
