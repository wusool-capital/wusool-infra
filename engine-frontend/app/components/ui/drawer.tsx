import { useEffect, useRef, useState, type ReactNode } from "react";

type DrawerProps = {
  title: string;
  status?: ReactNode;
  /** Primary actions shown before Close in the header. */
  actions: ReactNode;
  /** Shown under the header when an action is blocked. */
  notice?: ReactNode;
  /** When true, closing asks before discarding changes. */
  dirty?: boolean;
  onClose: () => void;
  children: ReactNode;
};

// The single layer allowed over a page (CLAUDE.md "One layer"): the discard check is
// an inline bar inside the drawer, never a second dialog.
export function Drawer({ title, status, actions, notice, dirty = false, onClose, children }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);

  const requestClose = () => (dirty ? setConfirmingDiscard(true) : onClose());

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    return () => {
      if (opener?.isConnected) opener.focus();
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  });

  return (
    <div className="drawer-layer">
      <div className="drawer-scrim" onClick={requestClose} />
      <div className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" tabIndex={-1} ref={panelRef}>
        <header className="drawer__head">
          <div className="drawer__titles">
            <h2 id="drawer-title" className="drawer__title">{title}</h2>
            {status && <p className="drawer__status">{status}</p>}
          </div>
          <div className="drawer__actions">
            {actions}
            <button type="button" className="button button--quiet" onClick={requestClose}>
              Close
            </button>
          </div>
        </header>
        {confirmingDiscard ? (
          <div className="drawer__notice" role="alert">
            <span>Discard your changes?</span>
            <button type="button" className="button button--small" onClick={onClose}>Discard</button>
            <button type="button" className="button button--small button--quiet" onClick={() => setConfirmingDiscard(false)}>Keep editing</button>
          </div>
        ) : (
          notice && <div className="drawer__notice" role="alert">{notice}</div>
        )}
        <div className="drawer__body">{children}</div>
      </div>
    </div>
  );
}
