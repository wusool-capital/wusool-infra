'use client';

import { useId, useState } from 'react';
import type { SpeakerLabel } from '@/types';
import type { SpeakerNames } from '@/hooks/useMeetingSpeakers';
import { diarizedIndex } from '@/lib/speakers';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Input } from './ui/input';
import { Button } from './ui/button';

interface SpeakerChipProps {
  label: SpeakerLabel;
  speakers: SpeakerNames;
}

export function SpeakerChip({ label, speakers }: SpeakerChipProps) {
  const name = speakers.resolveName(label);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const suggestionsId = useId();

  // Only diarized voices can be named; "me" comes from settings and "others" is not one person.
  const renameable = speakers.rename !== undefined && diarizedIndex(label) !== null;
  const chipClass = 'text-xs font-medium text-primary';

  if (!name) return null;
  if (!renameable) return <span className={chipClass}>{name}</span>;

  const save = async () => {
    const trimmed = draft.trim();
    if (!trimmed || !speakers.rename) return;
    setSaving(true);
    setError(null);
    try {
      await speakers.rename(label, trimmed);
      setOpen(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setDraft('');
      }}
    >
      <PopoverTrigger asChild>
        <button type="button" className={`${chipClass} hover:underline`} title="Name this speaker">
          {name}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 space-y-2" align="start">
        <p className="text-sm text-muted-foreground">
          Who is {name}? Everything they said in this meeting is updated, and future meetings recognise their voice.
        </p>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <Input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Name"
            list={suggestionsId}
          />
          <Button type="submit" size="sm" disabled={saving || !draft.trim()}>
            Save
          </Button>
        </form>
        <datalist id={suggestionsId}>
          {speakers.knownNames.map((known) => (
            <option key={known} value={known} />
          ))}
        </datalist>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </PopoverContent>
    </Popover>
  );
}
