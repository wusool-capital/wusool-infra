"use client"

import { useEffect, useState } from "react"
import { invoke } from "@tauri-apps/api/core"
import { Trash2 } from "lucide-react"
import type { SpeakerProfileSummary } from "@/lib/speakers"
import { Input } from "./ui/input"
import { Button } from "./ui/button"
import { Switch } from "./ui/switch"
import { ConfirmationModal } from "./ConfirmationModel/confirmation-modal"
import { SettingsRow, SettingsSection } from "./settings/SettingsSection"
import { useCoreMlModels } from "@/hooks/useCoreMlModels"
import { CoreMlDownloadDialog } from "./CoreMlDownloadDialog"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog"

export function SpeakerSettings() {
  const [selfName, setSelfName] = useState("")
  const [savedSelfName, setSavedSelfName] = useState("")
  const [justSaved, setJustSaved] = useState(false)
  const [profiles, setProfiles] = useState<SpeakerProfileSummary[]>([])
  const [pendingDelete, setPendingDelete] = useState<SpeakerProfileSummary | null>(null)
  const coreMl = useCoreMlModels()
  const backend = coreMl.settings
  const models = coreMl.models
  const [confirmingOff, setConfirmingOff] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoSeparate, setAutoSeparate] = useState(true)

  const loadProfiles = async () => setProfiles(await invoke<SpeakerProfileSummary[]>("list_speaker_profiles"))

  useEffect(() => {
    ;(async () => {
      try {
        const name = (await invoke<string | null>("get_self_speaker_name")) ?? ""
        setSelfName(name)
        setSavedSelfName(name)
        setAutoSeparate(await invoke<boolean>("get_auto_separate"))
        await loadProfiles()
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

  const toggleAutoSeparate = async (enabled: boolean) => {
    setError(null)
    setAutoSeparate(enabled)
    try {
      await invoke("set_auto_separate", { enabled })
    } catch (e) {
      setAutoSeparate(!enabled)
      setError(String(e))
    }
  }

  const toggleCoreMl = async (enabled: boolean) => {
    setError(null)
    if (!enabled) {
      // Nothing downloaded means nothing to keep or delete, so no question to ask.
      if (models?.coreml_ready) setConfirmingOff(true)
      else await coreMl.setBackend("cpu").catch((e) => setError(String(e)))
      return
    }
    // Already downloaded (kept after turning off last time): switch straight on, no dialog.
    if (models?.coreml_ready) {
      await coreMl.setBackend("coreml").catch((e) => setError(String(e)))
      return
    }
    coreMl.ask()
  }

  const turnOff = async (deleteModels: boolean) => {
    setConfirmingOff(false)
    try {
      await coreMl.setBackend("cpu")
      if (deleteModels) await invoke("delete_coreml_models")
      await coreMl.refresh()
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
      description="Scribe labels your microphone with your name and separates other voices in each meeting. Voice fingerprints stay on this device."
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

      <SettingsRow
        title="Separate Speakers Automatically"
        description={
          autoSeparate
            ? "Runs after every recording and import."
            : "Off. Use Separate Speakers in a meeting's transcript when you want it."
        }
        control={
          <Switch
            aria-label="Separate speakers automatically"
            checked={autoSeparate}
            onCheckedChange={toggleAutoSeparate}
          />
        }
      />

      {backend?.coreml_available && (
        <SettingsRow
          title="Faster Speaker Separation (CoreML)"
          description={
            models?.coreml_ready ? (
              "About 6× faster. Uses up to 2.7 GB of memory while it runs. Models downloaded."
            ) : coreMl.needsDownload ? (
              <>
                About 6× faster. Uses up to 2.7 GB of memory while it runs. Its models (about 300 MB) download the
                first time you separate speakers.{" "}
                <button
                  type="button"
                  onClick={coreMl.ask}
                  className="font-medium text-foreground underline underline-offset-2 hover:no-underline"
                >
                  Download now
                </button>
              </>
            ) : (
              "About 6× faster. Uses up to 2.7 GB of memory while it runs, and downloads about 300 MB once."
            )
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

      <CoreMlDownloadDialog
        coreMl={coreMl}
        description="Scribe needs a one-time download of about 300 MB of voice models. Speaker separation keeps working on the standard model until it finishes."
        skipLabel="Not Now"
        onDownloaded={() => void coreMl.setBackend("coreml").catch((e) => setError(String(e)))}
      />

      <Dialog open={confirmingOff} onOpenChange={setConfirmingOff}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>Turn Off Faster Speaker Separation?</DialogTitle>
            <DialogDescription>
              Also delete the downloaded CoreML models (about 270 MB)? If you delete them, turning this back on means
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
