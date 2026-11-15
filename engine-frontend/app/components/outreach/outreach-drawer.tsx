import { useState } from "react";
import { ENRICH_COST_CREDITS } from "../../demo/api";
import type { Counterparty, OutreachData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { findCodenameLeak } from "../../lib/codename";
import { defaultTemplate, draftBody, linkFor, summaryOf, templatesFor, type Template } from "../../lib/outreach";
import { Drawer } from "../ui/drawer";
import { useRouteAction } from "../ui/toast";

type Props = { row: Counterparty; data: OutreachData; onClose: () => void };

// PRD R2 and R3: Generate drafts the message (template by type); Send is the
// person's click. With no contact, Apollo enrichment shows its credit cost first.
export function OutreachDrawer({ row, data, onClose }: Props) {
  const act = useRouteAction("/outreach");
  const deal = byId(data.deals, row.dealId || undefined);
  const contacts = row.contactIds.map((id) => byId(data.people, id)).filter((person) => person !== undefined);
  const [contactId, setContactId] = useState(contacts[0]?.id ?? "");
  const [template, setTemplate] = useState<Template>(defaultTemplate(row));
  const [body, setBody] = useState(() => draftBody(template, row, deal, contacts[0]?.name ?? ""));
  const [edited, setEdited] = useState(false);

  // Contacts arrive after enrichment: pick the first and redraft if nothing was typed.
  if (!contactId && contacts[0]) {
    setContactId(contacts[0].id);
    if (!edited) setBody(draftBody(template, row, deal, contacts[0].name));
  }

  const contact = byId(data.people, contactId);
  const leak = findCodenameLeak(body, deal, contact);
  const blocker = !contact ? "" : leak ? `Remove "${leak}" before sending. Buyers only see the code name.` : !body.trim() ? "Write a message before sending." : "";
  const link = linkFor(row);

  const redraft = (next: Template, name = contact?.name ?? "") => {
    setTemplate(next);
    setBody(draftBody(next, row, deal, name));
    setEdited(false);
  };

  const send = () => {
    act({ intent: "outreach", id: row.id, contactId: contact!.id, template, link, summary: summaryOf(body) }, `${template} sent to ${contact!.name}. Demo: nothing was sent.`);
    onClose();
  };

  return (
    <Drawer
      title={row.name}
      status={deal ? deal.codeName : row.listName}
      dirty={edited}
      onClose={onClose}
      notice={blocker || undefined}
      actions={
        <button type="button" className="button" disabled={!contact || Boolean(blocker)} onClick={send}>
          Send
        </button>
      }
    >
      {contacts.length === 0 && (
        <section className="drawer__section">
          <h3 className="panel-heading">No contact yet</h3>
          <div className="credit-box">
            <p>
              Enrich with Apollo finds the key contacts. Costs {ENRICH_COST_CREDITS} credits; {data.apolloCreditsLeft} left this month.
            </p>
            <button
              type="button"
              className="button button--small"
              disabled={data.apolloCreditsLeft < ENRICH_COST_CREDITS}
              onClick={() => act({ intent: "enrich", id: row.id }, `${row.name} enriched for ${ENRICH_COST_CREDITS} credits.`)}
            >
              Enrich for {ENRICH_COST_CREDITS} credits
            </button>
          </div>
        </section>
      )}

      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Message</h3>
          <span className="badge">AI draft</span>
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="out-to">To</label>
            <select
              id="out-to"
              value={contactId}
              disabled={contacts.length === 0}
              onChange={(event) => {
                setContactId(event.target.value);
                if (!edited) setBody(draftBody(template, row, deal, byId(data.people, event.target.value)?.name ?? ""));
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
            <label htmlFor="out-template">Template</label>
            <select id="out-template" value={template} onChange={(event) => redraft(event.target.value as Template)}>
              {templatesFor(row).map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
        </div>
        <p className="muted">{link === "no link" ? "No link: owner approaches never share deal material." : `Includes ${link}, chosen by the NDA status.`}</p>
        <div className="field">
          <label htmlFor="out-body">Message</label>
          <textarea
            id="out-body"
            rows={9}
            value={body}
            onChange={(event) => {
              setBody(event.target.value);
              setEdited(true);
            }}
          />
        </div>
      </section>
    </Drawer>
  );
}
