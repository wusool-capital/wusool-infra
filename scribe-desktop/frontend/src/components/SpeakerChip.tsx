'use client';

import { useState } from 'react';
import type { SpeakerLabel } from '@/types';
import type { SpeakerNames } from '@/hooks/useMeetingSpeakers';
import { diarizedIndex } from '@/lib/speakers';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from './ui/command';

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

  // Only diarized voices can be named; "me" comes from settings and "others" is not one person.
  const renameable = speakers.rename !== undefined && diarizedIndex(label) !== null;
  const chipClass = 'text-xs font-medium text-foreground';

  if (!name) return null;
  if (!renameable) return <span className={chipClass}>{name}</span>;

  const save = async (value: string) => {
    const trimmed = value.trim();
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

  const typed = draft.trim();
  const matches = speakers.knownNames.filter((known) => known.toLowerCase().includes(typed.toLowerCase()));
  const typedIsKnown = speakers.knownNames.some((known) => known.toLowerCase() === typed.toLowerCase());

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setDraft('');
          setError(null);
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          // An unnamed voice keeps a dotted underline so it reads as something to fill in.
          className={`${chipClass} rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            speakers.isNamed(label) ? '' : 'underline decoration-dotted decoration-muted-foreground underline-offset-4'
          }`}
          aria-label={`Name ${name}`}
        >
          {name}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            autoFocus
            value={draft}
            onValueChange={setDraft}
            placeholder={`Who is ${name}?`}
            disabled={saving}
          />
          <CommandList>
            {(typed && !typedIsKnown) || matches.length > 0 ? (
              <CommandGroup>
                {/* Existing people first, so Enter picks a match instead of creating a near-duplicate. */}
                {matches.map((known) => (
                  <CommandItem key={known} value={known} onSelect={() => save(known)}>
                    {known}
                  </CommandItem>
                ))}
                {typed && !typedIsKnown && (
                  <CommandItem value={`new:${typed}`} onSelect={() => save(typed)}>
                    Name them &ldquo;{typed}&rdquo;
                  </CommandItem>
                )}
              </CommandGroup>
            ) : (
              <p className="px-3 py-2 text-xs text-muted-foreground">
                Type a name. Scribe will recognise this voice in later meetings.
              </p>
            )}
          </CommandList>
        </Command>
        {error && <p className="border-t border-border px-3 py-2 text-xs text-destructive">{error}</p>}
      </PopoverContent>
    </Popover>
  );
}
