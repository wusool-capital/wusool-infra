import { useState } from "react";

/** "Show more" pages belong to the loader data they were fetched for, so a filter change or save starts over. */
export function useMorePages<T extends { nextCursor: string | null }>(first: T, load: (cursor: string) => Promise<T>) {
  const [more, setMore] = useState<{ after: T; pages: T[] }>({ after: first, pages: [] });
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const pages = more.after === first ? [first, ...more.pages] : [first];
  const last = pages[pages.length - 1];

  const showMore = async () => {
    if (!last.nextCursor) return;
    setLoading(true);
    setFailed(false);
    try {
      const next = await load(last.nextCursor);
      setMore({ after: first, pages: [...pages.slice(1), next] });
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };

  return { pages, hasMore: last.nextCursor !== null, loading, failed, showMore };
}
