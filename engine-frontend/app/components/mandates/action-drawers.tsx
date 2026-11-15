import { useState } from "react";
import type { DealViewData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { Drawer } from "../ui/drawer";
import { useDealAction } from "./use-deal";

type PanelProps = { data: DealViewData; onClose: () => void };

// PRD MB2: Toolkit matching with the deal's profile prefilled. Names are added unenriched:
// no Apollo call and no AI enrichment at this point.
export function FindMoreDrawer({ data, onClose }: PanelProps) {
  const act = useDealAction();
  const [picked, setPicked] = useState<string[]>([]);
  const noun = data.deal.side === "sell" ? "buyers" : "targets";
  const toggle = (id: string) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);

  return (
    <Drawer
      title={`Find more ${noun}`}
      status={`Matched on ${data.deal.sector}, ${data.deal.city}`}
      dirty={picked.length > 0}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={picked.length === 0}
          onClick={() => {
            act({ intent: "add-suggestions", ids: JSON.stringify(picked) }, `${picked.length} ${noun} added, not enriched.`);
            onClose();
          }}
        >
          Add {picked.length || ""} {noun}
        </button>
      }
    >
      <section className="drawer__section">
        {data.suggestions.length === 0 ? (
          <p className="empty-state">No new matches.</p>
        ) : (
          <ul className="pick-list">
            {data.suggestions.map((s) => (
              <li key={s.id}>
                <label className="pick-list__item">
                  <input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s.id)} />
                  <span>
                    <span className="cell-title">{s.name}</span>
                    <span className="cell-sub">
                      {s.category}, {s.hq}. {s.rationale}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Drawer>
  );
}

// The next-step button for "Send the CIM to buyers who signed the NDA".
export function SendCimDrawer({ data, onClose }: PanelProps) {
  const act = useDealAction();
  const signed = data.counterparties.filter((row) => row.ndaSignedDate && row.status !== "Passed");
  const [body, setBody] = useState(
    `Dear [first name],\n\nThank you for signing the NDA on ${data.deal.codeName}. Your data room invitation is below. It holds the CIM, the financial pack and the reconciliation of normalised EBITDA.\n\nFirst-round offers are due on 12 Nov 2026. Happy to set up a call with management before then.\n\nBest regards,\nJules`,
  );
  const missingContact = signed.filter((row) => row.contactIds.length === 0);

  return (
    <Drawer
      title="Send the CIM to signed buyers"
      dirty={false}
      onClose={onClose}
      notice={missingContact.length ? `No contact for ${missingContact.map((row) => row.name).join(", ")}. Enrich them first.` : undefined}
      actions={
        <button
          type="button"
          className="button"
          disabled={signed.length === 0 || missingContact.length > 0}
          onClick={() => {
            act({ intent: "send-cim" }, `CIM sent to ${signed.length} buyers. Demo: nothing was sent.`);
            onClose();
          }}
        >
          Send to {signed.length} buyers
        </button>
      }
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Recipients</h3>
        <ul className="contact-list">
          {signed.map((row) => (
            <li key={row.id}>
              <span>{row.name}</span>
              <span className="muted">{row.contactIds.map((id) => byId(data.people, id)?.name).join(", ") || "No contact yet"}</span>
            </li>
          ))}
        </ul>
      </section>
      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Message</h3>
          <span className="badge">AI draft</span>
        </div>
        <div className="field">
          <label htmlFor="cim-body">Sent to each buyer, with their name filled in</label>
          <textarea id="cim-body" rows={10} value={body} onChange={(event) => setBody(event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}

// PRD MV1: Email client opens a draft from the deal owner's Gmail to the founder.
export function EmailClientDrawer({ data, onClose }: PanelProps) {
  const act = useDealAction();
  const client = data.deal.contactIds.map((id) => byId(data.people, id)).find((person) => person?.role === "client");
  const first = client?.name.split(" ")[0] ?? "";
  const inPlay = data.counterparties.filter((row) => row.status !== "Not contacted" && row.status !== "Passed").length;
  const draft = `Dear ${first},\n\nA short update on the process. ${inPlay} parties are engaged and ${data.offers.length} offers are in. Next: ${data.deal.nextStep.toLowerCase()}.\n\nHappy to talk it through this week.\n\nBest regards,\nJules`;
  const [body, setBody] = useState(draft);

  return (
    <Drawer
      title={`Email ${client?.name ?? "client"}`}
      status={client ? client.org : "No client contact on this deal"}
      dirty={body !== draft}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={!client || !body.trim()}
          onClick={() => {
            act({ intent: "email-client", recipient: client!.name }, `Email sent to ${client!.name}. Demo: nothing was sent.`);
            onClose();
          }}
        >
          Send
        </button>
      }
    >
      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Message</h3>
          <span className="badge">AI draft</span>
        </div>
        <div className="field">
          <label htmlFor="client-body">To {client?.name ?? "the client"}</label>
          <textarea id="client-body" rows={10} value={body} onChange={(event) => setBody(event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}

// PRD MH3: decision points record who decided what and why.
export function DecisionDrawer({ data, onClose }: PanelProps) {
  const act = useDealAction();
  const [text, setText] = useState("");
  const [why, setWhy] = useState("");
  const [counterpartyId, setCounterpartyId] = useState("");
  const tooShort = why.trim().length < 3;

  return (
    <Drawer
      title="Log a decision"
      dirty={Boolean(text || why)}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={!text.trim() || tooShort}
          onClick={() => {
            act({ intent: "decision", text: text.trim(), why: why.trim(), counterpartyId }, "Decision logged.");
            onClose();
          }}
        >
          Save
        </button>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="dec-text">Decision</label>
          <input id="dec-text" value={text} placeholder="For example: exclude Harrow Equity" onChange={(event) => setText(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="dec-why">Why</label>
          <textarea id="dec-why" rows={3} value={why} onChange={(event) => setWhy(event.target.value)} aria-describedby={why && tooShort ? "dec-why-error" : undefined} />
          {why && tooShort && <p id="dec-why-error" className="field-error">Give a reason of at least 3 characters.</p>}
        </div>
        <div className="field">
          <label htmlFor="dec-cp">About</label>
          <select id="dec-cp" value={counterpartyId} onChange={(event) => setCounterpartyId(event.target.value)}>
            <option value="">The whole deal</option>
            {data.counterparties.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </div>
      </section>
    </Drawer>
  );
}
