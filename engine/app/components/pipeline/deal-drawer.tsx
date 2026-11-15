import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { DEAL_STATUSES, type Deal, type DealPatch, type DealStatus, type Person, type User, type UserId } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatDate } from "../../lib/format";
import { STAGES, type Stage } from "../../lib/stages";
import { AmountInput } from "../ui/amount-input";
import { Drawer } from "../ui/drawer";
import type { NextAction } from "../../lib/next-action";
import { useRouteAction } from "../ui/toast";

// onDealPage: opened from the Deal view itself, where a "Deal view" link would lead nowhere.
// next: the deal's one next action (lib/next-action.ts), linking to the Deal view panel that does it.
type DealDrawerProps = { deal: Deal; users: User[]; people: Person[]; now: string; next: NextAction; onClose: () => void; onDealPage?: boolean };

function initialFields(deal: Deal) {
  return {
    stage: deal.stage,
    status: deal.status,
    ownerId: deal.ownerId,
    valueUsd: deal.valueUsd,
    nextStep: deal.nextStep,
    contactIds: deal.contactIds,
  };
}

export function DealDrawer({ deal, users, people, next, onClose, onDealPage }: DealDrawerProps) {
  const act = useRouteAction("/pipeline");
  const [params] = useSearchParams();
  // The Deal view's back link returns here with the same view and filters, drawer closed.
  const back = new URLSearchParams(params);
  back.delete("deal");
  const pipelineSearch = back.size ? `?${back}` : "";
  const [fields, setFields] = useState(() => initialFields(deal));
  const [blurb, setBlurb] = useState(deal.blurb);
  const fieldsDirty = JSON.stringify(fields) !== JSON.stringify(initialFields(deal));
  const blurbDirty = blurb !== deal.blurb;
  const valueInvalid = fields.valueUsd === 0;
  const leak = blurb.toLowerCase().includes(deal.clientName.toLowerCase());
  const set = (patch: Partial<typeof fields>) => setFields({ ...fields, ...patch });

  const save = () => {
    const patch: DealPatch = {
      stage: fields.stage,
      status: fields.status,
      ownerId: fields.ownerId,
      valueUsd: fields.valueUsd,
      nextStep: fields.nextStep.trim(),
      contactIds: fields.contactIds,
    };
    act({ intent: "deal-update", id: deal.id, patch: JSON.stringify(patch) }, `${deal.codeName} saved.`);
  };

  const approveBlurb = () => act({ intent: "blurb-approve", id: deal.id, blurb }, `Blurb approved for ${deal.codeName}.`);

  const contacts = fields.contactIds.map((id) => byId(people, id)).filter((person) => person !== undefined);
  const addable = people.filter((person) => !fields.contactIds.includes(person.id) && person.role !== "buyer");

  return (
    <Drawer
      title={deal.codeName}
      status={`${deal.side === "sell" ? "Sell-side" : "Buy-side"}, ${deal.sector}, ${deal.city}`}
      dirty={fieldsDirty || blurbDirty}
      onClose={onClose}
      actions={
        <>
          {!onDealPage && (
            <Link className="button button--quiet" to={`/deals/${deal.id}`} state={{ from: `/pipeline${pipelineSearch}` }}>
              Deal view
            </Link>
          )}
          <button type="button" className="button" disabled={!fieldsDirty || valueInvalid || !fields.nextStep.trim()} onClick={save}>
            Save
          </button>
        </>
      }
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Key fields</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="deal-stage">Stage</label>
            <select id="deal-stage" value={fields.stage} onChange={(event) => set({ stage: event.target.value as Stage })}>
              {STAGES.map((stage) => (
                <option key={stage}>{stage}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="deal-status">Status</label>
            <select id="deal-status" value={fields.status} onChange={(event) => set({ status: event.target.value as DealStatus })}>
              {DEAL_STATUSES.map((status) => (
                <option key={status}>{status}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="deal-owner">Owner</label>
            <select id="deal-owner" value={fields.ownerId} onChange={(event) => set({ ownerId: event.target.value as UserId })}>
              {users
                .filter((user) => user.role === "Advisor")
                .map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name}
                  </option>
                ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="deal-value">Expected deal value (USD)</label>
            <AmountInput
              id="deal-value"
              value={fields.valueUsd}
              aria-invalid={valueInvalid}
              aria-describedby={valueInvalid ? "deal-value-error" : undefined}
              onChange={(valueUsd) => set({ valueUsd })}
            />
            {valueInvalid && <p id="deal-value-error" className="field-error">Enter the full amount above 0, for example 7,500,000.</p>}
          </div>
        </div>
        <div className="field">
          <label htmlFor="deal-next">Next step</label>
          <input id="deal-next" value={fields.nextStep} onChange={(event) => set({ nextStep: event.target.value })} />
        </div>
        <p className="group-label">Contacts</p>
        {contacts.length === 0 && <p className="muted">No contact yet.</p>}
        <ul className="contact-list">
          {contacts.map((person) => (
            // Who they are, then how to reach them, each in its own column so nothing runs together.
            <li key={person.id} className="contact-row">
              <span className="contact-row__who">
                <span className="cell-title">{person.name}</span>
                <span className="cell-sub">{[person.title, person.org].filter(Boolean).join(", ")}</span>
              </span>
              {person.email ? <a className="contact-row__reach" href={`mailto:${person.email}`}>{person.email}</a> : <span className="contact-row__reach muted">No email</span>}
              {person.phone ? <a className="contact-row__reach" href={`tel:${person.phone.replace(/\s/g, "")}`}>{person.phone}</a> : <span className="contact-row__reach muted">No phone</span>}
              <button type="button" className="text-button" onClick={() => set({ contactIds: fields.contactIds.filter((id) => id !== person.id) })}>
                Remove<span className="visually-hidden"> {person.name}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="field field--inline">
          <label htmlFor="deal-add-contact">Add contact</label>
          <select
            id="deal-add-contact"
            value=""
            onChange={(event) => event.target.value && set({ contactIds: [...fields.contactIds, event.target.value] })}
          >
            <option value="">Choose a person</option>
            {addable.map((person) => (
              <option key={person.id} value={person.id}>
                {person.name}, {person.org}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Business blurb</h3>
          {deal.blurbApprovedAt && !blurbDirty ? (
            <span className="chip chip--done">Approved {formatDate(deal.blurbApprovedAt)}</span>
          ) : (
            <span className="badge">AI draft</span>
          )}
        </div>
        {deal.blurb || blurb ? (
          <>
            <div className="field">
              <label htmlFor="deal-blurb">Anonymised description for buyers</label>
              <textarea id="deal-blurb" rows={5} value={blurb} onChange={(event) => setBlurb(event.target.value)} />
            </div>
            {leak && <p className="field-error">Remove "{deal.clientName}" from the blurb. Buyers only see the code name.</p>}
            <button
              type="button"
              className="button button--small button--quiet"
              disabled={leak || !blurb.trim() || (Boolean(deal.blurbApprovedAt) && !blurbDirty)}
              onClick={approveBlurb}
            >
              Approve blurb
            </button>
          </>
        ) : (
          <p className="empty-state">No blurb yet.</p>
        )}
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Next</h3>
        <p className="muted">{next.reason}</p>
        <div className="button-row">
          <Link className="button" to={next.to} state={{ from: `/pipeline${pipelineSearch}` }}>
            {next.label}
          </Link>
        </div>
      </section>
    </Drawer>
  );
}
