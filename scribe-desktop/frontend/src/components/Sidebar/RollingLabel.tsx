import React, { useRef, useState } from 'react';
import { cn } from '@/lib/utils';

interface RollingLabelProps {
  text: string;
  className?: string;
}

// Roll speed in ms per px, with a floor so short overflows aren't a blink.
const ROLL_MS_PER_PX = 25;
const ROLL_MIN_MS = 800;

// Single-line label: ellipsis at rest, scrolls to reveal the tail on hover.
export function RollingLabel({ text, className }: RollingLabelProps) {
  const textRef = useRef<HTMLSpanElement>(null);
  const [distance, setDistance] = useState(0);

  const startRoll = () => {
    // Reduced-motion users keep the ellipsis; the title attribute shows the full name.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const el = textRef.current;
    if (!el) return;
    setDistance(Math.max(el.scrollWidth - el.clientWidth, 0));
  };

  const rollStyle = {
    '--roll-distance': `-${distance}px`,
    '--roll-duration': `${Math.max(distance * ROLL_MS_PER_PX, ROLL_MIN_MS)}ms`,
  } as React.CSSProperties;

  return (
    <span
      className={cn('block min-w-0 flex-1 overflow-hidden whitespace-nowrap', className)}
      title={text}
      onMouseEnter={startRoll}
      onMouseLeave={() => setDistance(0)}
    >
      {distance > 0 ? (
        <span className="inline-block animate-label-roll" style={rollStyle}>
          {text}
        </span>
      ) : (
        <span ref={textRef} className="block truncate">
          {text}
        </span>
      )}
    </span>
  );
}
