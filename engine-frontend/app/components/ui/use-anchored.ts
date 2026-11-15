import { useEffect, useRef, useState } from "react";

/**
 * Places a popover under its trigger, fixed to the screen. It is drawn at page level (a portal),
 * so a scrolling table or Home cell can neither cut it off nor fade it. A scroll or resize
 * would leave it floating away from its trigger, so either one closes it.
 */
/** Space a menu needs below its trigger before it opens upward instead. */
const ROOM_BELOW = 200;

export function useAnchored(open: boolean, close: () => void, align: "start" | "end" = "start") {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [style, setStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    if (!open) return;
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  });

  /** Call when opening, to read where the trigger is now. */
  const place = () => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    // Near the bottom of the screen the popover opens upward instead, so it is never cut off.
    const vertical = window.innerHeight - rect.bottom < ROOM_BELOW ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 };
    setStyle({ ...vertical, ...(align === "end" ? { right: window.innerWidth - rect.right } : { left: rect.left }) });
  };

  return { triggerRef, style, place };
}
