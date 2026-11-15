import { useState } from "react";
import type { Deal, Person } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { dayKey } from "../../lib/format";
import {
  AGREEMENT_DOCUMENTS,
  AGREEMENT_LABELS,
  FEE_TRIGGERS,
  GOVERNING_LAWS,
  LISTING_CHANNELS,
  NDA_LAWS,
  SIGNATORIES,
  STAKES,
  VAT_OPTIONS,
  defaultNdaDetails,
  defaultTerms,
  feeExamples,
  needsClientNda,
  type AgreementType,
  type ClientNdaDetails,
  type EngagementTerms,
} from "../../lib/engagement";
import { AmountInput } from "../ui/amount-input";
import { Drawer } from "../ui/drawer";
import { useDealAction } from "./use-deal";
import { Segmented } from "../ui/segmented";

type EngagementPanelProps = { deal: Deal; people: Person[]; now: string; onBack: () => void; onClose: () => void };

// Documents are drafted from the default terms when the panel opens, so the usual path is
// three clicks from the card: open, Draft engagement letter, Send (CLAUDE.md "3 clicks").
// Changing a term marks the documents out of date until "Update documents" is clicked.
export function EngagementPanel({ deal, people, now, onBack, onClose }: EngagementPanelProps) {
  const act = useDealAction();
  const recipient = deal.contactIds.map((id) => byId(people, id)).find((person) => person?.role === "client");
  const [terms, setTerms] = useState<EngagementTerms>(() => defaultTerms(deal, dayKey(now)));
  const [nda, setNda] = useState<ClientNdaDetails>(() => defaultNdaDetails(deal, recipient?.name ?? ""));
  const draftState = () => JSON.stringify({ terms, nda: needsClientNda(terms.agreement) ? nda : null });
  const [draftedFrom, setDraftedFrom] = useState(draftState);
  const documents = AGREEMENT_DOCUMENTS[terms.agreement];
  const [subject, setSubject] = useState(`Engagement letter for ${deal.clientName}`);
  const [body, setBody] = useState(() => defaultEmail(recipient, deal, documents));

  const stale = draftState() !== draftedFrom;
  const example = feeExamples(terms, deal.valueUsd);
  const withNda = needsClientNda(terms.agreement);
  const ndaMissing = withNda && [nda.legalName, nda.jurisdiction, nda.registration, nda.address, nda.clientSignatory].some((value) => !value.trim());
  const folder = `01. Deals/01. Pipeline/${deal.clientName}/01. Engagement Docs`;
  const set = <K extends keyof EngagementTerms>(key: K, value: EngagementTerms[K]) => setTerms({ ...terms, [key]: value });
  // The email lists the attached documents, so it follows the agreement type unless already edited.
  const switchAgreement = (type: AgreementType) => {
    if (body === defaultEmail(recipient, deal, documents)) setBody(defaultEmail(recipient, deal, AGREEMENT_DOCUMENTS[type]));
    set("agreement", type);
  };
  const setNdaField =<K extends keyof ClientNdaDetails>(key: K, value: ClientNdaDetails[K]) => setNda({ ...nda, [key]: value });
  const invalidNumber = Object.values(terms).some((value) => typeof value === "number" && !(value >= 0));
  const blocker = !recipient
    ? "Add a client contact to the deal before sending."
    : invalidNumber
      ? "Fix the highlighted terms before sending."
      : ndaMissing
        ? "Fill the company's legal details for the confidentiality agreement."
      : stale
        ? "Terms changed. Update the documents before sending."
        : "";

  const send = () => {
    act({ intent: "engagement-send", id: deal.id }, `Engagement letter sent to ${recipient?.name} with ${documents.length} attachments. Demo: nothing was sent.`);
    onClose();
  };

  return (
    <Drawer
      title={`Engagement letter: ${deal.codeName}`}
      dirty
      onClose={onClose}
      notice={blocker}
      actions={
        <>
          <button type="button" className="button button--quiet" onClick={onBack}>
            Back
          </button>
          <button type="button" className="button" disabled={Boolean(blocker)} onClick={send}>
            Send
          </button>
        </>
      }
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Terms</h3>
        {deal.side === "sell" && (
          <Segmented className="segmented--block" role="group" aria-label="Agreement type">
            {(["sell-structured", "sell-listing"] as AgreementType[]).map((type) => (
              <button key={type} type="button" className="segmented__option" aria-pressed={terms.agreement === type} onClick={() => switchAgreement(type)}>
                {AGREEMENT_LABELS[type]}
              </button>
            ))}
          </Segmented>
        )}

        {terms.agreement === "sell-structured" && (
          <div className="form-grid">
            <NumberField id="t-client" label="Success fee, buyers the client brings (%)" value={terms.clientBuyerFeePct} onChange={(v) => set("clientBuyerFeePct", v)} />
            <NumberField id="t-ours" label="Success fee, buyers we bring (%)" value={terms.ourBuyerFeePct} onChange={(v) => set("ourBuyerFeePct", v)} />
            <AmountField id="t-retainer" label="Retainer per month (USD), credited" value={terms.retainerUsd} onChange={(v) => set("retainerUsd", v)} />
            <NumberField id="t-months" label="Retainer, up to (months)" whole value={terms.retainerMonths} onChange={(v) => set("retainerMonths", v)} />
            <SelectField id="t-stake" label="Stake for sale" value={terms.stake} options={STAKES} onChange={(v) => set("stake", v)} />
          </div>
        )}

        {terms.agreement === "sell-listing" && (
          <>
            <div className="form-grid">
              <NumberField id="t-fee" label="Success fee (%)" value={terms.listingFeePct} onChange={(v) => set("listingFeePct", v)} />
              <AmountField id="t-min" label="Minimum fee (USD)" value={terms.listingMinUsd} onChange={(v) => set("listingMinUsd", v)} />
              <SelectField id="t-law" label="Governing law" value={terms.law} options={GOVERNING_LAWS} onChange={(v) => set("law", v)} />
              <SelectField id="t-vat" label="VAT" value={terms.vat} options={VAT_OPTIONS} onChange={(v) => set("vat", v)} />
              <NumberField id="t-term" label="Term (months)" whole value={terms.termMonths} onChange={(v) => set("termMonths", v)} />
            </div>
            <SelectField id="t-trigger" label="Fee is due on" value={terms.feeTrigger} options={FEE_TRIGGERS} onChange={(v) => set("feeTrigger", v)} />
            <SelectField id="t-channels" label="Listing channels" value={terms.channels} options={LISTING_CHANNELS} onChange={(v) => set("channels", v)} />
          </>
        )}

        {terms.agreement === "buy" && (
          <div className="form-grid">
            <NumberField id="t-tier1" label="Tier 1, introductions: success fee (%)" value={terms.tier1FeePct} onChange={(v) => set("tier1FeePct", v)} />
            <NumberField id="t-tier2" label="Tier 2, full support: success fee (%)" value={terms.tier2FeePct} onChange={(v) => set("tier2FeePct", v)} />
            <AmountField id="t-tier2-min" label="Tier 2 minimum fee (USD)" value={terms.tier2MinUsd} onChange={(v) => set("tier2MinUsd", v)} />
            <AmountField id="t-retainer" label="Tier 2 retainer per month (USD), credited" value={terms.retainerUsd} onChange={(v) => set("retainerUsd", v)} />
            <NumberField id="t-months" label="Tier 2 retainer, up to (months)" whole value={terms.retainerMonths} onChange={(v) => set("retainerMonths", v)} />
          </div>
        )}

        <div className="form-grid">
          {terms.agreement !== "sell-listing" && (
            <>
              <div className="field">
                <label htmlFor="t-kickoff">Kickoff</label>
                <input id="t-kickoff" type="date" value={terms.kickoff} onChange={(event) => set("kickoff", event.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="t-close">Target closing</label>
                <input id="t-close" type="month" value={terms.targetClose} onChange={(event) => set("targetClose", event.target.value)} />
              </div>
            </>
          )}
          <SelectField id="t-signatory" label="Wusool signatory" value={terms.signatory} options={SIGNATORIES} onChange={(v) => set("signatory", v)} />
        </div>

        <div className="fee-example" aria-live="polite">
          <p className="group-label">Fee at the expected deal value</p>
          {example.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {example.warning && <p className="field-error">{example.warning}</p>}
        </div>
      </section>

      {withNda && (
        <section className="drawer__section">
          <h3 className="panel-heading">Confidentiality agreement</h3>
          <TextField id="n-name" label="Company legal name" value={nda.legalName} onChange={(v) => setNdaField("legalName", v)} required />
          <div className="form-grid">
            <TextField id="n-jurisdiction" label="Incorporated in" value={nda.jurisdiction} onChange={(v) => setNdaField("jurisdiction", v)} required />
            <TextField id="n-registration" label="Registration number" value={nda.registration} onChange={(v) => setNdaField("registration", v)} required />
          </div>
          <TextField id="n-address" label="Registered office" value={nda.address} onChange={(v) => setNdaField("address", v)} required />
          <div className="form-grid">
            <TextField id="n-signatory" label="Signs for the company" value={nda.clientSignatory} onChange={(v) => setNdaField("clientSignatory", v)} required />
            <SelectField id="n-law" label="Governing law" value={nda.law} options={NDA_LAWS} onChange={(v) => setNdaField("law", v)} />
          </div>
          <TextField
            id="n-sectors"
            label="Competitor sectors (no designs or partner terms shared with these buyers without approval)"
            value={nda.competitorSectors}
            onChange={(v) => setNdaField("competitorSectors", v)}
          />
        </section>
      )}

      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Documents</h3>
          {stale ? <span className="chip chip--alert">Out of date</span> : <span className="badge">AI draft</span>}
        </div>
        <p className="muted">Saved to {folder}</p>
        <ul className="doc-list">
          {documents.map((doc) => (
            <li key={doc.name}>
              <span>{doc.name}</span>
              <span className="muted">Skill: {doc.skill}</span>
            </li>
          ))}
        </ul>
        {stale && (
          <button type="button" className="button button--small" disabled={invalidNumber} onClick={() => setDraftedFrom(draftState())}>
            Update documents
          </button>
        )}
      </section>

      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Email</h3>
          <span className="badge">AI draft</span>
        </div>
        <p className="muted">
          {recipient ? `To ${recipient.name}, ${recipient.org}. From your Gmail, with the documents attached.` : "No client contact on this deal yet."}
        </p>
        <div className="field">
          <label htmlFor="e-subject">Subject</label>
          <input id="e-subject" value={subject} onChange={(event) => setSubject(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="e-body">Message</label>
          <textarea id="e-body" rows={9} value={body} onChange={(event) => setBody(event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}

// The cover email never states fees; they live in the attached documents.
function defaultEmail(recipient: Person | undefined, deal: Deal, documents: { short: string }[]) {
  const firstName = recipient?.name.split(" ")[0] ?? "";
  const names = documents.map((doc) => doc.short);
  const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names[0];
  return `Dear ${firstName},\n\nThank you for your time this week. Please find attached ${list} for ${deal.clientName}.\n\nOnce you are happy with the terms, we will send the documents for e-signature and plan the kickoff.\n\nBest regards,\nJules`;
}

function TextField(props: { id: string; label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  const missing = props.required && !props.value.trim();
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <input id={props.id} value={props.value} aria-invalid={missing} onChange={(event) => props.onChange(event.target.value)} />
      {missing && <p className="field-error">Needed for the confidentiality agreement.</p>}
    </div>
  );
}

// Percentages may have decimals; months ("whole") may not.
function NumberField(props: { id: string; label: string; value: number; onChange: (value: number) => void; whole?: boolean }) {
  const invalid = !(props.value >= 0);
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <input
        id={props.id}
        inputMode={props.whole ? "numeric" : "decimal"}
        value={Number.isNaN(props.value) ? "" : String(props.value)}
        aria-invalid={invalid}
        onChange={(event) => {
          const text = props.whole ? event.target.value.split(".")[0].replace(/\D/g, "") : event.target.value;
          props.onChange(text === "" ? NaN : Number(text));
        }}
      />
      {invalid && <p className="field-error">Enter a number, 0 or more.</p>}
    </div>
  );
}

/** Money in whole US dollars with comma separators; empty counts as invalid. */
function AmountField(props: { id: string; label: string; value: number; onChange: (value: number) => void }) {
  const invalid = Number.isNaN(props.value);
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <AmountInput id={props.id} value={props.value} aria-invalid={invalid} onChange={(value) => props.onChange(value ?? NaN)} />
      {invalid && <p className="field-error">Enter the full amount, for example 5,000.</p>}
    </div>
  );
}

function SelectField<T extends string>(props: { id: string; label: string; value: T; options: readonly T[]; onChange: (value: T) => void }) {
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <select id={props.id} value={props.value} onChange={(event) => props.onChange(event.target.value as T)}>
        {props.options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}
