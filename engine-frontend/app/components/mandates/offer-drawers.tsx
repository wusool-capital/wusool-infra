import { useState } from "react";
import type { DealViewData, Offer, OfferInput, OfferStatus } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { dayKey, formatDate, formatMoney } from "../../lib/format";
import { AmountInput } from "../ui/amount-input";
import { Drawer } from "../ui/drawer";
import { useDealAction } from "./use-deal";

// Demo stand-in for PRD MO3: an LOI attached to an email, read by a small model.
// The fields are a draft; the advisor checks each one before saving.
const ATTACHMENTS: Record<string, { name: string; extracted: OfferInput }[]> = {
  "d-falcon": [
    {
      name: "Petra IOI 11 Nov.pdf",
      extracted: { counterpartyId: "c-petra", type: "IOI", date: "2026-11-11", evUsd: 11_800_000, cashPct: 80, deferredPct: 20, earnoutPct: 0, conditions: "Vet licences transfer before closing", ddWeeks: 8, exclusivityWeeks: 4, status: "Received", documentName: "Petra IOI 11 Nov.pdf" },
    },
  ],
};

type Props = { data: DealViewData; onClose: () => void };

export function AddOfferDrawer({ data, onClose }: Props) {
  const act = useDealAction();
  const attachments = (ATTACHMENTS[data.deal.id] ?? []).filter((a) => !data.offers.some((o) => o.documentName === a.name));
  const blank: OfferInput = {
    counterpartyId: data.counterparties[0]?.id ?? "",
    type: "IOI",
    date: dayKey(data.now),
    evUsd: 0,
    cashPct: 100,
    deferredPct: 0,
    earnoutPct: 0,
    conditions: "",
    ddWeeks: 8,
    exclusivityWeeks: 4,
    status: data.deal.side === "sell" ? "Received" : "Sent",
  };
  const [offer, setOffer] = useState<OfferInput>(blank);
  const [fromAttachment, setFromAttachment] = useState("");
  const set = <K extends keyof OfferInput>(key: K, value: OfferInput[K]) => setOffer({ ...offer, [key]: value });
  const split = offer.cashPct + offer.deferredPct + offer.earnoutPct;
  const error = !offer.counterpartyId ? "Choose who made the offer." : !(offer.evUsd > 0) ? "Enter the enterprise value." : split !== 100 ? `Cash, deferred and earn-out add up to ${split}%. They must add up to 100%.` : "";

  const pickAttachment = (name: string) => {
    setFromAttachment(name);
    const found = attachments.find((a) => a.name === name);
    setOffer(found ? found.extracted : blank);
  };

  return (
    <Drawer
      title="Add offer"
      status={fromAttachment ? `From ${fromAttachment}` : undefined}
      dirty={JSON.stringify(offer) !== JSON.stringify(blank)}
      onClose={onClose}
      notice={offer.evUsd > 0 ? error : undefined}
      actions={
        <button
          type="button"
          className="button"
          disabled={Boolean(error)}
          onClick={() => {
            act({ intent: "add-offer", offer: JSON.stringify(offer) }, `Offer from ${byId(data.counterparties, offer.counterpartyId)?.name} saved.`);
            onClose();
          }}
        >
          Save offer
        </button>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="of-source">Source</label>
          <select id="of-source" value={fromAttachment} onChange={(event) => pickAttachment(event.target.value)}>
            <option value="">By hand</option>
            {attachments.map((a) => (
              <option key={a.name} value={a.name}>
                Email attachment: {a.name}
              </option>
            ))}
          </select>
        </div>
        {fromAttachment && <p className="badge">AI draft: check each field</p>}
        <div className="form-grid">
          <div className="field">
            <label htmlFor="of-cp">{data.deal.side === "sell" ? "Buyer" : "Target"}</label>
            <select id="of-cp" value={offer.counterpartyId} onChange={(event) => set("counterpartyId", event.target.value)}>
              {data.counterparties.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="of-type">Type</label>
            <select id="of-type" value={offer.type} onChange={(event) => set("type", event.target.value as Offer["type"])}>
              <option>IOI</option>
              <option>LOI</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="of-date">Date</label>
            <input id="of-date" type="date" value={offer.date} onChange={(event) => set("date", event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="of-ev">Enterprise value (USD)</label>
            <AmountInput id="of-ev" value={offer.evUsd || undefined} onChange={(value) => set("evUsd", value ?? 0)} />
          </div>
          <WholeField id="of-cash" label="Cash at close (%)" value={offer.cashPct} onChange={(v) => set("cashPct", v)} />
          <WholeField id="of-deferred" label="Deferred (%)" value={offer.deferredPct} onChange={(v) => set("deferredPct", v)} />
          <WholeField id="of-earnout" label="Earn-out (%)" value={offer.earnoutPct} onChange={(v) => set("earnoutPct", v)} />
          <WholeField id="of-dd" label="Due diligence (weeks)" value={offer.ddWeeks} onChange={(v) => set("ddWeeks", v)} />
          <WholeField id="of-excl" label="Exclusivity asked (weeks)" value={offer.exclusivityWeeks} onChange={(v) => set("exclusivityWeeks", v)} />
        </div>
        <div className="field">
          <label htmlFor="of-cond">Conditions</label>
          <textarea id="of-cond" rows={3} value={offer.conditions} onChange={(event) => set("conditions", event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}

function WholeField({ id, label, value, onChange }: { id: string; label: string; value: number; onChange: (value: number) => void }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} inputMode="numeric" value={String(value)} onChange={(event) => onChange(Number(event.target.value.split(".")[0].replace(/\D/g, "")) || 0)} />
    </div>
  );
}

const STATUS_ACTIONS: { label: string; status: OfferStatus; needsWhy: boolean }[] = [
  { label: "Accept", status: "Accepted", needsWhy: true },
  { label: "Reject", status: "Rejected", needsWhy: true },
  { label: "Mark under review", status: "Under review", needsWhy: false },
];

// Accepting or rejecting is a decision point: who decided and why go to History (PRD MH3).
export function OfferDrawer({ offer, data, onClose }: Props & { offer: Offer }) {
  const act = useDealAction();
  const [why, setWhy] = useState("");
  const buyer = byId(data.counterparties, offer.counterpartyId);
  const decide = (status: OfferStatus) => {
    act({ intent: "offer-status", id: offer.id, status, why: why.trim() }, `${buyer?.name} ${offer.type} marked ${status.toLowerCase()}.`);
    onClose();
  };

  return (
    <Drawer
      title={`${buyer?.name} ${offer.type}`}
      status={`${formatDate(offer.date)}. ${offer.status}.`}
      dirty={Boolean(why)}
      onClose={onClose}
      actions={
        <>
          {STATUS_ACTIONS.filter((a) => a.status !== offer.status).map((a, index) => (
            <button key={a.status} type="button" className={index === 0 ? "button" : "button button--quiet"} disabled={a.needsWhy && why.trim().length < 3} onClick={() => decide(a.status)}>
              {a.label}
            </button>
          ))}
        </>
      }
    >
      <section className="drawer__section">
        <dl className="label-grid label-grid--two">
          <div className="label-grid__item"><dt>Enterprise value</dt><dd>{formatMoney(offer.evUsd)}</dd></div>
          <div className="label-grid__item"><dt>Cash, deferred, earn-out</dt><dd>{offer.cashPct}%, {offer.deferredPct}%, {offer.earnoutPct}%</dd></div>
          <div className="label-grid__item"><dt>Due diligence</dt><dd>{offer.ddWeeks} weeks</dd></div>
          <div className="label-grid__item"><dt>Exclusivity asked</dt><dd>{offer.exclusivityWeeks} weeks</dd></div>
          <div className="label-grid__item"><dt>Conditions</dt><dd>{offer.conditions || "None"}</dd></div>
          <div className="label-grid__item"><dt>Document</dt><dd>{offer.documentName ?? <span className="muted">Not set</span>}</dd></div>
        </dl>
      </section>
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="offer-why">Why (needed to accept or reject)</label>
          <textarea id="offer-why" rows={3} value={why} onChange={(event) => setWhy(event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}
