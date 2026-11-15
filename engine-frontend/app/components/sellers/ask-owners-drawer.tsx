import { useState } from "react";
import type { Person, SellerResult } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { count, formatDate } from "../../lib/format";
import { ownerApproachBody, summaryOf } from "../../lib/outreach";
import { Drawer } from "../ui/drawer";

export type OwnerNote = { id: string; contactId: string; summary: string };

type Props = { rows: SellerResult[]; people: Person[]; onSend: (notes: OwnerNote[]) => void; onClose: () => void };

// PRD S3: one AI draft per owner, each readable and editable; one click sends the ones still ticked.
// Owners without a contact, or already asked, are listed with the reason and never sent.
export function AskOwnersDrawer({ rows, people, onSend, onClose }: Props) {
  const ready = rows.filter((row) => !row.approachedOn && byId(people, row.contactIds[0]));
  const skipped = rows.filter((row) => !ready.includes(row));
  const [included, setIncluded] = useState(ready.map((row) => row.id));
  const [bodies, setBodies] = useState<Record<string, string>>(() =>
    Object.fromEntries(ready.map((row) => [row.id, ownerApproachBody(byId(people, row.contactIds[0])!.name, row.rationale)])),
  );
  const [edited, setEdited] = useState(false);
  const sending = ready.filter((row) => included.includes(row.id));
  const blocker = sending.length === 0 ? "Tick at least one owner to send." : sending.some((row) => !bodies[row.id].trim()) ? "Write a message for every ticked owner." : "";

  const send = () =>
    onSend(sending.map((row) => ({ id: row.id, contactId: row.contactIds[0], summary: summaryOf(bodies[row.id]) })));

  return (
    <Drawer
      title={`Ask ${count(rows.length, "owner", "owners")} if open to selling`}
      dirty={edited}
      notice={ready.length > 0 && blocker ? blocker : undefined}
      onClose={onClose}
      actions={
        <button type="button" className="button" disabled={Boolean(blocker)} onClick={send}>
          Send {count(sending.length, "note", "notes")}
        </button>
      }
    >
      {ready.map((row) => {
        const contact = byId(people, row.contactIds[0])!;
        return (
          <section key={row.id} className="drawer__section">
            <div className="drawer__section-head">
              <label className="owner-note__pick">
                <input
                  type="checkbox"
                  checked={included.includes(row.id)}
                  onChange={() => setIncluded((ids) => (ids.includes(row.id) ? ids.filter((id) => id !== row.id) : [...ids, row.id]))}
                />
                <span className="panel-heading">{row.name}</span>
              </label>
              <span className="badge">AI draft</span>
            </div>
            <p className="muted owner-note__to">
              To {contact.name}
              {contact.title && `, ${contact.title}`}
            </p>
            <div className="field">
              <label htmlFor={`note-${row.id}`} className="visually-hidden">
                Message to {contact.name}
              </label>
              <textarea
                id={`note-${row.id}`}
                rows={6}
                value={bodies[row.id]}
                disabled={!included.includes(row.id)}
                onChange={(event) => {
                  setBodies({ ...bodies, [row.id]: event.target.value });
                  setEdited(true);
                }}
              />
            </div>
          </section>
        );
      })}

      {skipped.length > 0 && (
        <section className="drawer__section">
          <h3 className="panel-heading">Not included</h3>
          <ul className="plain-list">
            {skipped.map((row) => (
              <li key={row.id}>
                <span className="cell-title">{row.name}</span>
                <span className="cell-sub">
                  {row.approachedOn ? `Already asked on ${formatDate(row.approachedOn)}. Follow up from Outreach.` : "No owner contact yet. Enrich it first."}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Drawer>
  );
}
