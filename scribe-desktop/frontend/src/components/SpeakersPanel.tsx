"use client";

import { useEffect, useId, useRef, useState } from 'react';
import { Play, Square } from 'lucide-react';
import type { SpeakerLabel } from '@/types';
import type { SpeakerNames } from '@/hooks/useMeetingSpeakers';
import { useVoiceClip } from '@/hooks/useVoiceClip';
import { formatTalkTime, SpeakerOverview } from '@/lib/speakers';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Spinner } from './ui/spinner';

interface SpeakersPanelProps {
  meetingId: string;
  speakers: SpeakerNames;
  /** Scrolls the transcript to a line, loading more of it if needed. */
  onShowLine: (segmentId: string) => void;
  /** Asks to separate this meeting's speakers from scratch; absent while a run is going. */
  onSeparateAgain?: () => void;
}

const MAX_OPTIONS = 5;

/** Names every separated voice in one place, so nobody has to scroll the transcript to find them. */
export function SpeakersPanel({ meetingId, speakers, onShowLine, onSeparateAgain }: SpeakersPanelProps) {
  const voices = speakers.overview;
  const unnamed = voices.filter((v) => v.name === null);
  // Set once voices load: open if anyone is unnamed. Naming the last voice keeps it open.
  const [expandedChoice, setExpanded] = useState<boolean | null>(null);
  const expanded = expandedChoice ?? false;
  const hasVoices = voices.length > 0;
  const startOpen = unnamed.length > 0;
  useEffect(() => {
    if (hasVoices) setExpanded((current) => current ?? startOpen);
  }, [hasVoices, startOpen]);
  // "No" only hides a suggestion for this visit; it is a hint, not a decision worth storing.
  const [dismissed, setDismissed] = useState<Set<SpeakerLabel>>(new Set());
  const [editing, setEditing] = useState<SpeakerLabel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputs = useRef(new Map<SpeakerLabel, HTMLInputElement>());
  const clip = useVoiceClip(meetingId);

  if (voices.length === 0 || !speakers.rename) return null;

  const save = async (label: SpeakerLabel, name: string) => {
    const trimmed = name.trim();
    if (!trimmed || !speakers.rename) return;
    setError(null);
    try {
      await speakers.rename(label, trimmed);
      setEditing(null);
      // Move straight on to the next voice still waiting for a name.
      const next = unnamed.find((v) => v.label !== label);
      if (next) requestAnimationFrame(() => inputs.current.get(next.label)?.focus());
    } catch (e) {
      setError(String(e));
    }
  };

  const toConfirm = voices.filter((v) => v.auto_named && v.name !== null).length;
  const status =
    (unnamed.length === 0 ? `All ${voices.length} named` : `${unnamed.length} of ${voices.length} to name`) +
    (toConfirm > 0 ? ` · ${toConfirm} to confirm` : '');

  return (
    <section aria-labelledby="who-spoke-heading" className="border-b border-border bg-card px-4 py-3">
      <div className="flex items-center gap-3">
        <h2 id="who-spoke-heading" className="text-sm font-semibold text-foreground">
          Who Spoke?
        </h2>
        <span className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
          {status}
        </span>
        {onSeparateAgain && (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={onSeparateAgain}>
            Separate Again
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          className={onSeparateAgain ? undefined : 'ml-auto'}
          aria-expanded={expanded}
          aria-controls="who-spoke-list"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Hide' : unnamed.length === 0 ? 'Edit Names' : 'Show'}
        </Button>
      </div>

      {expanded && (
        <ul id="who-spoke-list" className="mt-2 divide-y divide-border">
          {voices.map((voice) => (
            <VoiceRow
              key={voice.label}
              voice={voice}
              displayName={speakers.resolveName(voice.label) ?? voice.label}
              // Names already in this meeting stay listed: picking one combines the two voices, with Undo.
              options={speakers.knownNames.filter((n) => n.toLowerCase() !== voice.name?.toLowerCase())}
              mergeTargetFor={(name) => speakers.mergeTargetFor(voice.label, name)}
              suggestion={voice.suggestion && !dismissed.has(voice.label) ? voice.suggestion.name : null}
              isEditing={voice.name === null || editing === voice.label}
              clip={clip}
              inputRef={(el) => {
                if (el) inputs.current.set(voice.label, el);
                else inputs.current.delete(voice.label);
              }}
              onSave={(name) => save(voice.label, name)}
              onDismissSuggestion={() => {
                setDismissed((prev) => new Set(prev).add(voice.label));
                requestAnimationFrame(() => inputs.current.get(voice.label)?.focus());
              }}
              onEdit={() => {
                setEditing(voice.label);
                requestAnimationFrame(() => inputs.current.get(voice.label)?.focus());
              }}
              onCancelEdit={() => setEditing(null)}
              onShowLine={onShowLine}
            />
          ))}
        </ul>
      )}

      {(error || clip.error) && (
        <p className="mt-2 text-sm text-destructive" role="alert">
          {error ?? `Couldn't play this voice: ${clip.error}`}
        </p>
      )}
    </section>
  );
}

interface VoiceRowProps {
  voice: SpeakerOverview;
  displayName: string;
  options: string[];
  mergeTargetFor: (name: string) => string | null;
  suggestion: string | null;
  isEditing: boolean;
  clip: ReturnType<typeof useVoiceClip>;
  inputRef: (el: HTMLInputElement | null) => void;
  onSave: (name: string) => Promise<void>;
  onDismissSuggestion: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onShowLine: (segmentId: string) => void;
}

function VoiceRow({
  voice,
  displayName,
  options,
  mergeTargetFor,
  suggestion,
  isEditing,
  clip,
  inputRef,
  onSave,
  onDismissSuggestion,
  onEdit,
  onCancelEdit,
  onShowLine,
}: VoiceRowProps) {
  const isPlaying = clip.playing === voice.label;
  const isLoading = clip.loading === voice.label;
  const lines = `${voice.line_count} ${voice.line_count === 1 ? 'line' : 'lines'}`;

  return (
    <li className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto_minmax(0,15rem)] items-center gap-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground" title={displayName}>
          {displayName}
        </p>
        <p className="text-xs text-muted-foreground tabular-nums">
          {formatTalkTime(voice.talk_seconds)} · {lines}
          {voice.auto_named && !isEditing && ' · recognised by voice'}
        </p>
      </div>

      {voice.sample ? (
        <button
          type="button"
          className="min-w-0 truncate rounded-sm text-left text-sm text-muted-foreground hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title={`Show in transcript: ${voice.sample.text}`}
          onClick={() => voice.sample && onShowLine(voice.sample.segment_id)}
        >
          &ldquo;{voice.sample.text}&rdquo;
        </button>
      ) : (
        <span />
      )}

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label={isPlaying ? `Stop ${displayName}'s voice` : `Play ${displayName}'s voice`}
        disabled={!voice.sample || isLoading}
        onClick={() => voice.sample && void clip.toggle(voice.label, voice.sample)}
      >
        {isLoading ? <Spinner className="h-4 w-4" /> : isPlaying ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
      </Button>

      <div className="min-w-0">
        {!isEditing ? (
          <div className="flex items-center justify-end gap-1">
            {/* Recognised automatically: a wrong match would mislabel every line, so ask once. */}
            {voice.auto_named && voice.name && (
              <Button variant="outline" size="sm" onClick={() => voice.name && void onSave(voice.name)}>
                Confirm
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={onEdit}>
              Change
            </Button>
          </div>
        ) : suggestion ? (
          <div className="flex items-center gap-2">
            {/* Wraps rather than truncates: the name is the point of the suggestion. */}
            <span className="min-w-0 flex-1 text-sm leading-tight text-foreground">
              Sounds like <strong className="font-semibold">{suggestion}</strong>?
            </span>
            <Button variant="outline" size="sm" onClick={() => void onSave(suggestion)}>
              Yes
            </Button>
            <Button variant="ghost" size="sm" onClick={onDismissSuggestion}>
              No
            </Button>
          </div>
        ) : (
          <NameField
            label={voice.label}
            displayName={displayName}
            initial={voice.name ?? ''}
            options={options}
            mergeTargetFor={mergeTargetFor}
            inputRef={inputRef}
            onSave={onSave}
            onCancel={voice.name !== null ? onCancelEdit : undefined}
          />
        )}
      </div>
    </li>
  );
}

interface NameFieldProps {
  label: SpeakerLabel;
  displayName: string;
  initial: string;
  options: string[];
  mergeTargetFor: (name: string) => string | null;
  inputRef: (el: HTMLInputElement | null) => void;
  onSave: (name: string) => Promise<void>;
  onCancel?: () => void;
}

/** A name box that offers people already in the voice library as you type. */
function NameField({ label, displayName, initial, options, mergeTargetFor, inputRef, onSave, onCancel }: NameFieldProps) {
  const [value, setValue] = useState(initial);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [saving, setSaving] = useState(false);
  // Enter or a picked suggestion moves focus on, so its blur must not save a second time; Escape must not save at all.
  const settledRef = useRef(false);
  const listId = useId();
  const hintId = useId();
  const combinesWith = value.trim() !== initial.trim() ? mergeTargetFor(value) : null;

  const typed = value.trim().toLowerCase();
  const matches = (typed ? options.filter((o) => o.toLowerCase().includes(typed)) : options)
    .sort((a, b) => Number(!a.toLowerCase().startsWith(typed)) - Number(!b.toLowerCase().startsWith(typed)))
    .slice(0, MAX_OPTIONS);
  const showList = open && matches.length > 0;

  const commit = async (name: string) => {
    if (!name.trim() || settledRef.current) return;
    settledRef.current = true;
    setSaving(true);
    setOpen(false);
    try {
      await onSave(name);
    } finally {
      settledRef.current = false;
      setSaving(false);
    }
  };

  // Leaving the box saves what was typed, since there is no Save button; an unchanged name just closes editing.
  const handleBlur = () => {
    setOpen(false);
    if (settledRef.current) return;
    if (value.trim() && value.trim() !== initial.trim()) void commit(value);
    else if (initial) onCancel?.();
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        name={`speaker-name-${label}`}
        aria-label={`Name for ${displayName}`}
        autoComplete="off"
        spellCheck={false}
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        aria-describedby={hintId}
        placeholder="Name…"
        className="h-8"
        value={value}
        disabled={saving}
        onChange={(e) => {
          setValue(e.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => {
          settledRef.current = false;
          setOpen(true);
        }}
        onBlur={handleBlur}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' && matches.length > 0) {
            e.preventDefault();
            setOpen(true);
            setActive((i) => (i + 1) % matches.length);
          } else if (e.key === 'ArrowUp' && matches.length > 0) {
            e.preventDefault();
            setActive((i) => (i <= 0 ? matches.length - 1 : i - 1));
          } else if (e.key === 'Enter') {
            e.preventDefault();
            void commit(showList && active >= 0 ? matches[active] : value);
          } else if (e.key === 'Escape') {
            if (showList) {
              setOpen(false);
            } else {
              settledRef.current = true;
              setValue(initial);
              onCancel?.();
            }
          }
        }}
      />
      {saving && <Spinner className="absolute right-2 top-2 h-4 w-4" />}
      {/* Always mounted so screen readers announce the note when it appears. */}
      <p id={hintId} aria-live="polite" className={combinesWith ? 'mt-1 text-xs text-muted-foreground' : 'sr-only'}>
        {combinesWith && `Saving combines this voice with ${combinesWith}.`}
      </p>
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-md border border-border bg-popover py-1 shadow-md"
        >
          {matches.map((option, i) => (
            <li
              key={option}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`cursor-pointer truncate px-3 py-1.5 text-sm text-popover-foreground ${i === active ? 'bg-foreground/10' : 'hover:bg-foreground/10'}`}
              // mousedown, not click, so the input keeps focus and doesn't close the list first.
              onMouseDown={(e) => {
                e.preventDefault();
                void commit(option);
              }}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate">{option}</span>
                {mergeTargetFor(option) && <span className="shrink-0 text-xs text-muted-foreground">Combines lines</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
