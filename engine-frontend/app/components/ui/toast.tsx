import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useSubmit } from "react-router";

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
