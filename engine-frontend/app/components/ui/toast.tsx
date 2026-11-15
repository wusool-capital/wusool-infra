import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useFetcher, useSubmit } from "react-router";
import type { ActionResult } from "../../lib/action-result";

type NoticeContextValue = { notice: string; setNotice: (text: string) => void };

const NoticeContext = createContext<NoticeContextValue>({ notice: "", setNotice: () => {} });

const NOTICE_MS = 8000;

/** Holds the one-line confirmation shown after an action, on any page. */
export function NoticeProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  return <NoticeContext.Provider value={{ notice, setNotice }}>{children}</NoticeContext.Provider>;
}

export function Toast() {
  const { notice } = useContext(NoticeContext);
  return (
    <p className="toast" role="status" data-visible={notice ? "yes" : "no"}>
      {notice}
    </p>
  );
}

/** Shows a one-line confirmation for something done in the browser only (copy to clipboard). */
export function useNotice() {
  return useContext(NoticeContext).setNotice;
}

/**
 * Posts an intent to a route action without navigating, then shows a notice.
 * Demo actions cannot fail, so the notice is set at once.
 */
export function useRouteAction(action: string) {
  const submit = useSubmit();
  const { setNotice } = useContext(NoticeContext);

  return (fields: Record<string, string>, notice?: string) => {
    submit(fields, { method: "post", action, navigate: false });
    if (notice) setNotice(notice);
  };
}

/** Posts a save and waits for the answer, so a refused write keeps the drawer open for a retry. */
export function useSaveAction(action: string) {
  const fetcher = useFetcher<ActionResult>();
  const { setNotice } = useContext(NoticeContext);
  const after = useRef<{ notice: string; onDone: () => void } | null>(null);

  useEffect(() => {
    if (fetcher.state !== "idle" || !fetcher.data || fetcher.data.error || !after.current) return;
    const { notice, onDone } = after.current;
    after.current = null;
    setNotice(notice);
    onDone();
  }, [fetcher.state, fetcher.data, setNotice]);

  return {
    save: (fields: Record<string, string>, notice: string, onDone: () => void) => {
      after.current = { notice, onDone };
      void fetcher.submit(fields, { method: "post", action });
    },
    saving: fetcher.state !== "idle",
    error: fetcher.state === "idle" ? fetcher.data?.error : undefined,
  };
}
