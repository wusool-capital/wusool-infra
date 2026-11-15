import { useLayoutEffect, useRef, useState, type CSSProperties, type HTMLAttributes, type ReactNode } from "react";

type Props = { as?: "div" | "nav"; className?: string; children: ReactNode } & Omit<HTMLAttributes<HTMLElement>, "className" | "children">;

const SELECTED = '[aria-pressed="true"], [aria-selected="true"], .active';

/**
 * A segmented switch whose white highlight slides to the picked option, so the eye follows
 * the change. The options stay plain buttons or links with aria-pressed, aria-selected or
 * the router's "active" class; the highlight is measured from whichever one is selected.
 */
export function Segmented({ as: Tag = "div", className = "", children, ...rest }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [thumb, setThumb] = useState<CSSProperties>({ opacity: 0 });

  // Runs after every render: a parent re-renders whenever the selection changes.
  useLayoutEffect(() => {
    const place = () => {
      const selected = ref.current?.querySelector<HTMLElement>(SELECTED);
      const next = selected ? { left: selected.offsetLeft, width: selected.offsetWidth } : { opacity: 0 };
      setThumb((current) => (current.left === next.left && current.width === next.width && current.opacity === next.opacity ? current : next));
    };
    place();
    // The selected label turns semibold, which widens it after the first paint.
    const frame = requestAnimationFrame(place);
    window.addEventListener("resize", place);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", place);
    };
  });

  return (
    <Tag ref={ref} className={`segmented segmented--sliding ${className}`.trim()} {...rest}>
      <span className="segmented__thumb" style={thumb} aria-hidden="true" />
      {children}
    </Tag>
  );
}
