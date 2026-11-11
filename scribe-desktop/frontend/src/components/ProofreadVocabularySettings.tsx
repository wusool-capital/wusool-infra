"use client"

import { useEffect, useState, type FormEvent } from "react"
import { invoke } from "@tauri-apps/api/core"
import { Plus, X } from "lucide-react"
import { toast } from "sonner"
import { Button } from "./ui/button"
import { Input } from "./ui/input"
import { SettingsRow, SettingsSection } from "./settings/SettingsSection"
import {
  MAX_VOCABULARY_WORDS,
  addVocabularyWords,
  removeVocabularyWord,
} from "@/lib/proofreadVocabulary"

/** Extra names and terms Proofread should spell correctly, on top of the server's built-in list. */
export function ProofreadVocabularySettings() {
  const [words, setWords] = useState<string[]>([])
  const [draft, setDraft] = useState("")

  useEffect(() => {
    invoke<string[]>("get_proofread_vocabulary")
      .then(setWords)
      .catch(() => setWords([]))
  }, [])

  const save = async (next: string[]) => {
    const previous = words
    setWords(next)
    try {
      setWords(await invoke<string[]>("set_proofread_vocabulary", { words: next }))
    } catch (error) {
      setWords(previous)
      toast.error("Could not save your vocabulary", { description: String(error) })
    }
  }

  const add = (event: FormEvent) => {
    event.preventDefault()
    const typed = draft.split(/[,\n]/).filter((word) => word.trim()).length
    const next = addVocabularyWords(words, draft)
    const added = next.length - words.length
    setDraft("")
    if (added > 0) void save(next)
    if (added < typed) {
      toast.info(
        next.length >= MAX_VOCABULARY_WORDS
          ? `Your vocabulary is full at ${MAX_VOCABULARY_WORDS} words, so some weren't added.`
          : added === 0
            ? "Already in your vocabulary."
            : `Added ${added}; the rest were already in your vocabulary.`,
      )
    }
  }

  const full = words.length >= MAX_VOCABULARY_WORDS

  return (
    <SettingsSection
      title="Proofread"
      description="Proofread already knows common deal, finance and GCC terms. Add names and terms it should also spell correctly, such as client companies or project code names."
    >
      <SettingsRow
        title="Your Vocabulary"
        htmlFor="proofread-vocabulary"
        description={`${words.length} of ${MAX_VOCABULARY_WORDS}. Separate several with commas.`}
      >
        <form onSubmit={add} className="flex max-w-xl gap-2">
          <Input
            id="proofread-vocabulary"
            name="proofread-vocabulary"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={full ? "List is full" : "Add a name or term…"}
            disabled={full}
          />
          <Button type="submit" size="icon" aria-label="Add to vocabulary" disabled={full || !draft.trim()}>
            <Plus />
          </Button>
        </form>
        {words.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2" aria-label="Your vocabulary">
            {words.map((word) => (
              <li
                key={word}
                className="flex items-center gap-1 rounded-full border border-border bg-background py-1 pl-3 pr-1 text-sm text-foreground"
              >
                <span className="max-w-[16rem] truncate" title={word}>
                  {word}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${word}`}
                  onClick={() => void save(removeVocabularyWord(words, word))}
                  className="flex size-6 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="size-3.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">No words added yet.</p>
        )}
      </SettingsRow>
    </SettingsSection>
  )
}
