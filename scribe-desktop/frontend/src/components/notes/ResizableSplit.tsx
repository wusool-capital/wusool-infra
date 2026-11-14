'use client';

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

const MIN_RATIO = 0.25;
const MAX_RATIO = 0.75;
const KEY_STEP = 0.05;
// The transcript toolbar needs ~480px; notes stay usable down to ~280px.
const MIN_LEFT_PX = 480;
const MIN_RIGHT_PX = 280;

/** Ratio bounds, tightened so neither pane drops below its pixel minimum. */
function clamp(ratio: number, width?: number): number {
  let min = MIN_RATIO;
  let max = MAX_RATIO;
  if (width && width >= MIN_LEFT_PX + MIN_RIGHT_PX) {
    min = Math.max(min, MIN_LEFT_PX / width);
    max = Math.min(max, 1 - MIN_RIGHT_PX / width);
  }
  return Math.min(max, Math.max(min, ratio));
}

interface ResizableSplitProps {
  left: ReactNode;
  right: ReactNode;
  /** localStorage key for the remembered ratio. */
  storageKey: string;
  leftLabel: string;
  rightLabel: string;
  /** Starting share of the left pane, before the user drags. */
  defaultRatio?: number;
  className?: string;
}

/** Two panes with a draggable, keyboard-operable divider. */
export function ResizableSplit({
  left,
  right,
  storageKey,
  leftLabel,
  rightLabel,
  defaultRatio = 0.5,
  className,
}: ResizableSplitProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [ratio, setRatio] = useState(defaultRatio);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    try {
      const saved = Number(localStorage.getItem(storageKey));
      if (saved > 0) setRatio(clamp(saved));
    } catch {
      // Storage unavailable: keep the default.
    }
  }, [storageKey]);

  const persist = useCallback(
    (next: number) => {
      try {
        localStorage.setItem(storageKey, String(next));
      } catch {
        // Not worth surfacing; the split still works for this session.
      }
    },
    [storageKey],
  );

  const handlePointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !containerRef.current) return;
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    setDragging(true);
    document.body.style.cursor = 'col-resize';
    const rect = containerRef.current.getBoundingClientRect();
    let latest = ratio;

    const onMove = (ev: globalThis.PointerEvent) => {
      latest = clamp((ev.clientX - rect.left) / rect.width, rect.width);
      setRatio(latest);
    };
    const onUp = () => {
      handle.removeEventListener('pointermove', onMove);
      handle.removeEventListener('pointerup', onUp);
      handle.removeEventListener('pointercancel', onUp);
      document.body.style.cursor = '';
      setDragging(false);
      persist(latest);
    };
    handle.addEventListener('pointermove', onMove);
    handle.addEventListener('pointerup', onUp);
    handle.addEventListener('pointercancel', onUp);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const delta = e.key === 'ArrowLeft' ? -KEY_STEP : e.key === 'ArrowRight' ? KEY_STEP : 0;
    if (!delta) return;
    e.preventDefault();
    const next = clamp(ratio + delta, containerRef.current?.clientWidth);
    setRatio(next);
    persist(next);
  };

  const reset = () => {
    setRatio(defaultRatio);
    persist(defaultRatio);
  };

  return (
    <div ref={containerRef} className={cn('flex h-full w-full min-w-0', className)}>
      <section
        aria-label={leftLabel}
        className="h-full overflow-hidden"
        // CSS mins also cover a ratio saved at a wider window size.
        style={{ width: `${ratio * 100}%`, minWidth: `min(${MIN_LEFT_PX}px, 60%)` }}
      >
        {left}
      </section>
      <div
        role="separator"
        tabIndex={0}
        aria-orientation="vertical"
        aria-label={`Resize ${leftLabel} and ${rightLabel}`}
        aria-valuemin={MIN_RATIO * 100}
        aria-valuemax={MAX_RATIO * 100}
        aria-valuenow={Math.round(ratio * 100)}
        title="Drag to resize. Double-click to reset."
        onPointerDown={handlePointerDown}
        onKeyDown={handleKeyDown}
        onDoubleClick={reset}
        className="group relative z-10 -mx-[3px] w-[7px] shrink-0 cursor-col-resize outline-none"
      >
        <div
          aria-hidden
          className={cn(
            'absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors duration-150',
            'group-hover:w-[3px] group-hover:bg-primary/40 group-focus-visible:w-[3px] group-focus-visible:bg-primary/60',
            dragging && 'w-[3px] bg-primary/60',
          )}
        />
      </div>
      <section
        aria-label={rightLabel}
        className="h-full flex-1 overflow-hidden"
        style={{ minWidth: `min(${MIN_RIGHT_PX}px, 40%)` }}
      >
        {right}
      </section>
    </div>
  );
}
