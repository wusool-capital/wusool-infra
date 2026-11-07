"use client"

import { useEffect, useState } from "react"
import { invoke } from "@tauri-apps/api/core"
import { Trash2 } from "lucide-react"
import type { SpeakerProfileSummary } from "@/lib/speakers"
import { Input } from "./ui/input"
import { Button } from "./ui/button"

export function SpeakerSettings() {
  const [selfName, setSelfName] = useState("")
  const [savedSelfName, setSavedSelfName] = useState("")
  const [profiles, setProfiles] = useState<SpeakerProfileSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  const loadProfiles = async () => setProfiles(await invoke<SpeakerProfileSummary[]>("list_speaker_profiles"))

  useEffect(() => {
    ;(async () => {
      try {
        const name = (await invoke<string | null>("get_self_speaker_name")) ?? ""
        setSelfName(name)
        setSavedSelfName(name)
        await loadProfiles()
      } catch (e) {
        setError(String(e))
      }
    })()
  }, [])

  const saveSelfName = async () => {
    try {
      await invoke("set_self_speaker_name", { name: selfName.trim() || null })
      setSavedSelfName(selfName.trim())
      setError(null)
    } catch (e) {
      setError(String(e))
    }
  }

  const deleteProfile = async (profile: SpeakerProfileSummary) => {
    if (!window.confirm(`Forget ${profile.name}'s voice? Past meetings keep their text but lose this name.`)) return
    try {
      await invoke("delete_speaker_profile", { profileId: profile.id })
      await loadProfiles()
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="bg-card rounded-lg border border-border p-6 shadow-sm space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-foreground mb-2">Speakers</h3>
        <p className="text-sm text-muted-foreground">
          Your microphone is labelled with your name. Other voices are separated after each meeting; name one once and
          Scribe recognises them in later meetings. Voice fingerprints stay on this device.
        </p>
      </div>

      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          saveSelfName()
        }}
      >
        <label className="flex-1 space-y-1">
          <span className="text-sm font-medium text-foreground">Your name</span>
          <Input value={selfName} onChange={(e) => setSelfName(e.target.value)} placeholder="Me" />
        </label>
        <Button type="submit" disabled={selfName.trim() === savedSelfName}>
          Save
        </Button>
      </form>

      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">Recognised voices</p>
        {profiles.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None yet. Click a speaker&apos;s name in a meeting transcript to name them.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border">
            {profiles.map((profile) => (
              <li key={profile.id} className="flex items-center justify-between px-3 py-2">
                <span className="text-sm text-foreground">
                  {profile.name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {profile.sample_count} {profile.sample_count === 1 ? "meeting" : "meetings"}
                  </span>
                </span>
                <Button variant="ghost" size="sm" onClick={() => deleteProfile(profile)} aria-label={`Forget ${profile.name}`}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
