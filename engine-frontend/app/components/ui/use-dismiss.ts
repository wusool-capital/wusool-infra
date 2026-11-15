import { useEffect, useRef } from "react";

/**
 * Closes a popover on a press outside it, or when keyboard focus moves outside it.
 * A blur check alone closed the panel when someone clicked an option's label text,
 * because that click moves focus nowhere (relatedTarget is null).
 */
export function useDismiss<T extends HTMLElement, P extends HTMLElement = HTMLElement>(open: boolean, close: () => void) {
  const ref = useRef<T>(null);
  // A panel drawn elsewhere in the page (a portal) still counts as inside.
  const panelRef = useRef<P>(null);
  const inside = (node: Node | null) => Boolean(node && (ref.current?.contains(node) || panelRef.current?.contains(node)));

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (ref.current && !inside(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  });

  const onBlur = (event: React.FocusEvent<T>) => {
    if (event.relatedTarget && !inside(event.relatedTarget)) close();
  };

  return { ref, panelRef, onBlur };
}
