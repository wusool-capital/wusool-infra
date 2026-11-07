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

type DiarizationBackend = "cpu" | "coreml"

// Mirrors the Rust `DiarizationBackendSettings` serialization.
interface DiarizationBackendSettings {
  backend: DiarizationBackend
  coreml_available: boolean
}

export function SpeakerSettings() {
  const [selfName, setSelfName] = useState("")
  const [savedSelfName, setSavedSelfName] = useState("")
  const [justSaved, setJustSaved] = useState(false)
  const [profiles, setProfiles] = useState<SpeakerProfileSummary[]>([])
  const [pendingDelete, setPendingDelete] = useState<SpeakerProfileSummary | null>(null)
  const [backend, setBackend] = useState<DiarizationBackendSettings | null>(null)
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

  const toggleCoreMl = async (enabled: boolean) => {
    const next: DiarizationBackend = enabled ? "coreml" : "cpu"
    try {
      await invoke("set_diarization_backend", { backend: next })
      setBackend((current) => (current ? { ...current, backend: next } : current))
      setError(null)
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
          description="About 6× faster. Uses up to 2.7 GB of memory while it runs, and downloads 260 MB once."
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

      <ConfirmationModal
        isOpen={pendingDelete !== null}
        text={`Forget ${pendingDelete?.name ?? "this person"}'s voice? Past meetings keep their text but lose this name, and Scribe stops recognising them.`}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </SettingsSection>
  )
}
