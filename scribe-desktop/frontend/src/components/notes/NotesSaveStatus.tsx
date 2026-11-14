import type { NotesSaveState } from '@/lib/notesAutosave';
import { cn } from '@/lib/utils';

const LABELS: Record<NotesSaveState, string> = {
  idle: '',
  saving: 'Saving…',
  saved: 'Saved',
  error: "Couldn't save. Keep typing to retry.",
  too_long: 'Notes are too long to save. Shorten them to keep saving.',
};

interface NotesSaveStatusProps {
  state: NotesSaveState;
  /** Overrides the label once saved, e.g. while a server sync is pending. */
  savedLabel?: string;
  className?: string;
}

export function NotesSaveStatus({ state, savedLabel, className }: NotesSaveStatusProps) {
  const label = state === 'saved' && savedLabel ? savedLabel : LABELS[state];
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn(
        'text-xs tabular-nums',
        state === 'error' || state === 'too_long' ? 'text-destructive' : 'text-muted-foreground',
        className,
      )}
    >
      {label}
    </span>
  );
}
