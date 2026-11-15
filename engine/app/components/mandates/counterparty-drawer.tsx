import { useState } from "react";
import { ENRICH_COST_CREDITS } from "../../demo/api";
import { COUNTERPARTY_STATUSES, type Counterparty, type CounterpartyStatus, type DealViewData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { findCodenameLeak } from "../../lib/codename";
import { formatDate, formatWhen } from "../../lib/format";
import { defaultTemplate, draftBody as draftFor, linkFor, summaryOf, templatesFor, type Template } from "../../lib/outreach";
import { Drawer } from "../ui/drawer";
import { StatusPill } from "./status-pill";
import { useDealAction } from "./use-deal";

const draftBody = (template: Template, row: Counterparty, data: DealViewData, contactName: string) => draftFor(template, row, data.deal, contactName);

type DrawerProps = { row: Counterparty; data: DealViewData; onClose: () => void };

export function CounterpartyDrawer({ row, data, onClose }: DrawerProps) {
  const act = useDealAction();
  const contacts = row.contactIds.map((id) => byId(data.people, id)).filter((person) => person !== undefined);
  const [status, setStatus] = useState<CounterpartyStatus>(row.status);
  const [nextStep, setNextStep] = useState(row.nextStep);
  const [contactId, setContactId] = useState(contacts[0]?.id ?? "");
  const [template, setTemplate] = useState<Template>(defaultTemplate(row));
  const contactName = byId(data.people, contactId)?.name ?? "";
  const [body, setBody] = useState(() => draftBody(template, row, data, contactName));
  const [bodyEdited, setBodyEdited] = useState(false);

  // Contacts arrive after enrichment; pick the first one and redraft if nothing was typed yet.
  const contact = byId(data.people, contactId) ?? contacts[0];
  if (!contactId && contacts[0]) {
    setContactId(contacts[0].id);
    if (!bodyEdited) setBody(draftBody(template, row, data, contacts[0].name));
  }

  const statusDirty = status !== row.status || nextStep !== row.nextStep;
  const leak = findCodenameLeak(body, data.deal, contact);
  const canEnrich = data.apolloCreditsLeft >= ENRICH_COST_CREDITS;
  const sendBlocker = !contact ? "No contact yet. Enrich with Apollo to find one." : leak ? `Remove "${leak}" before sending. Buyers only see the code name.` : !body.trim() ? "Write a message before sending." : "";
  const history = data.history.filter((event) => event.counterpartyId === row.id);

  const send = () => {
    act({ intent: "outreach", id: row.id, contactId: contact!.id, template, link: linkFor(row), summary: summaryOf(body) }, `${template} sent to ${contact!.name}. Demo: nothing was sent.`);
    onClose();
  };

  return (
    <Drawer
      title={row.name}
      status={`${row.category}, ${row.hq}${row.ndaSignedDate ? `. NDA signed ${formatDate(row.ndaSignedDate)}` : ""}`}
      dirty={statusDirty || bodyEdited}
      onClose={onClose}
      notice={sendBlocker && contact ? sendBlocker : undefined}
      actions={
        <button type="button" className="button" disabled={Boolean(sendBlocker)} onClick={send}>
          Send {template.toLowerCase()}
        </button>
      }
    >
      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Status</h3>
          <StatusPill status={row.status} />
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="cp-status">Status</label>
            <select id="cp-status" value={status} onChange={(event) => setStatus(event.target.value as CounterpartyStatus)}>
              {COUNTERPARTY_STATUSES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cp-next">Next step</label>
            <input id="cp-next" value={nextStep} onChange={(event) => setNextStep(event.target.value)} />
          </div>
        </div>
        <button
          type="button"
          className="button button--small button--quiet"
          disabled={!statusDirty || !nextStep.trim()}
          onClick={() => act({ intent: "counterparty", id: row.id, patch: JSON.stringify({ status, nextStep: nextStep.trim() }) }, `${row.name} saved.`)}
        >
          Save status
        </button>
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Why this {data.deal.side === "sell" ? "buyer" : "target"}</h3>
        <p>{row.rationale}</p>
        <p className="muted">{row.website}</p>
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Contacts</h3>
        {contacts.length === 0 && <p className="muted">No contact yet.</p>}
        <ul className="contact-list">
          {contacts.map((person) => (
            <li key={person.id}>{person.name}</li>
          ))}
        </ul>
        <div className="credit-box">
          <p>
            Enrich with Apollo finds {contacts.length ? "more contacts" : "the key contacts"} at {row.name}. Costs {ENRICH_COST_CREDITS} credits; {data.apolloCreditsLeft} left this month.
          </p>
          <button
            type="button"
            className="button button--small"
            disabled={!canEnrich}
            onClick={() => act({ intent: "enrich", id: row.id }, `${row.name} enriched for ${ENRICH_COST_CREDITS} credits.`)}
          >
            Enrich for {ENRICH_COST_CREDITS} credits
          </button>
        </div>
      </section>

      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Outreach</h3>
          <span className="badge">AI draft</span>
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="cp-contact">To</label>
            <select
              id="cp-contact"
              value={contactId}
              disabled={contacts.length === 0}
              onChange={(event) => {
                setContactId(event.target.value);
                if (!bodyEdited) setBody(draftBody(template, row, data, byId(data.people, event.target.value)?.name ?? ""));
              }}
            >
              {contacts.length === 0 && <option value="">No contact yet</option>}
              {contacts.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cp-template">Template</label>
            <select
              id="cp-template"
              value={template}
              onChange={(event) => {
                const next = event.target.value as Template;
                setTemplate(next);
                setBody(draftBody(next, row, data, contactName));
                setBodyEdited(false);
              }}
            >
              {templatesFor(row).map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
        </div>
        <p className="muted">Includes {linkFor(row)}, chosen by the NDA status.</p>
        <div className="field">
          <label htmlFor="cp-body">Message</label>
          <textarea
            id="cp-body"
            rows={9}
            value={body}
            onChange={(event) => {
              setBody(event.target.value);
              setBodyEdited(true);
            }}
          />
        </div>
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">History</h3>
        {history.length === 0 ? (
          <p className="muted">Nothing logged yet.</p>
        ) : (
          <ul className="feed">
            {history.map((event) => (
              <li key={event.id} className="feed-item">
                <span className="feed-item__text">{event.text}</span>
                <span className="feed-item__when">{formatWhen(event.at, data.now)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Drawer>
  );
}
