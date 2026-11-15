import type { ReactNode } from "react";
import type { EmailLogEntry } from "../../demo/types";
import { formatDate } from "../../lib/format";
import { ActionsMenu, type MenuAction } from "./actions-menu";

// Pieces shared by the Buyers and Sellers record drawers.

export function LabelItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="label-grid__item">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

type HeaderProps<P extends string> = { itemName: string; actions: readonly MenuAction<P>[]; onEdit: () => void; onPick: (panel: P) => void };

/** Edit is one click from the record; the other actions sit in the "..." menu beside it. */
export function RecordHeaderActions<P extends string>({ itemName, actions, onEdit, onPick }: HeaderProps<P>) {
  return (
    <>
      <button type="button" className="button button--quiet" onClick={onEdit}>
        Edit
      </button>
      <ActionsMenu itemName={itemName} actions={actions} onPick={onPick} size="header" />
    </>
  );
}

/** Subject and date of each Gmail thread with the company, newest first. */
export function EmailLogSection({ org, emails }: { org: string; emails: EmailLogEntry[] }) {
  const threads = emails.filter((email) => email.org === org).sort((a, b) => b.date.localeCompare(a.date));
  return (
    <section className="drawer__section">
      <h3 className="panel-heading">Emails</h3>
      {threads.length === 0 ? (
        <p className="muted">No emails with this company yet.</p>
      ) : (
        <ul className="email-log">
          {threads.map((email) => (
            <li key={email.id} className="email-log__item">
              <span className="email-log__subject">{email.subject}</span>
              <span className="email-log__date">{formatDate(email.date)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
