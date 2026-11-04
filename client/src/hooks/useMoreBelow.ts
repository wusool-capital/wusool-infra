import { useCallback, useEffect, useRef, useState } from "react";

// Whether a scroll box has content below its fold, kept current as it scrolls or its content grows.
export function useMoreBelow(): [(node: HTMLElement | null) => void, boolean] {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [moreBelow, setMoreBelow] = useState(false);
  const frame = useRef(0);

  const attach = useCallback((el: HTMLElement | null) => {
    setNode(el);
  }, []);

  useEffect(() => {
    if (!node) return;
    const measure = (): void => {
      cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(() => {
        setMoreBelow(
          node.scrollHeight - node.scrollTop - node.clientHeight > 1,
        );
      });
    };
    measure();
    node.addEventListener("scroll", measure, { passive: true });
    const resize = new ResizeObserver(measure);
    resize.observe(node);
    for (const child of Array.from(node.children)) resize.observe(child);
    const mutations = new MutationObserver(measure);
    mutations.observe(node, { childList: true, subtree: true });
    return () => {
      cancelAnimationFrame(frame.current);
      node.removeEventListener("scroll", measure);
      resize.disconnect();
      mutations.disconnect();
    };
  }, [node]);

  return [attach, moreBelow];
}
