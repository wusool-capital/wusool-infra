import { useState } from "react";
import { OPEN_TO_SELLING, type NewSellerInput, type SellerPatch, type SellerRole, type SellersUniverseData } from "../../demo/types";
import { getSellerDetails } from "../../api";
import { changedFields } from "../../lib/action-result";
import { byId } from "../../lib/by-id";
import { isLive } from "../../lib/data-mode";
import { useDetails } from "../../lib/use-details";
import { formatDate, formatMoney, formatWhen } from "../../lib/format";
import { ownerApproachBody, summaryOf } from "../../lib/outreach";
import { StatusPill } from "../mandates/status-pill";
import { LeadDrawer } from "../pipeline/lead-drawer";
import { EmailLogSection, LabelItem as Item, RecordHeaderActions } from "../ui/record-parts";
import { AmountInput } from "../ui/amount-input";
import { DetailFields } from "../ui/detail-fields";
import { DetailValues } from "../ui/detail-values";
import { Drawer } from "../ui/drawer";
import { LinkText } from "../ui/link-text";
import { useRouteAction, useSaveAction } from "../ui/toast";
import { OpenToSellingPill } from "./open-to-selling-pill";

export const SELLER_ACTIONS = [
  { panel: "approach", label: "Ask if open to selling" },
  { panel: "add", label: "Add to a buy-side deal" },
  { panel: "lead", label: "New sell-side lead" },
  { panel: "edit", label: "Edit profile" },
] as const;
export type SellerPanel = (typeof SELLER_ACTIONS)[number]["panel"];

/** Asking only makes sense while the owner's appetite is Unknown; once Interested or a Warm intro, the answer is in. */
export function sellerActions(seller: SellerRole) {
  return SELLER_ACTIONS.map((action) => ({
    ...action,
    // Live greys out all but Edit until mandates and outreach are connected.
    disabled: (isLive && action.panel !== "edit") || (action.panel === "approach" && seller.openToSelling !== "Unknown"),
  }));
}

const ROUTE = "/sellers/universe";

/** The empty seller behind "Add seller". */
export const NEW_SELLER: SellerRole = {
  id: "new",
  name: "",
  hq: "",
  website: "",
  sector: "",
  geography: "",
  estRevenueUsd: null,
  openToSelling: "Unknown",
  ownerId: null,
  contactIds: [],
  notes: "",
};

type Props = {
  seller: SellerRole;
  data: SellersUniverseData;
  panel: SellerPanel | null;
  onPanel: (panel: SellerPanel | null) => void;
  onClose: () => void;
};

// PRD U1: the record drawer is read only. Each "..." action replaces its content in place,
// so the page keeps one layer.
export function SellerDrawer({ seller, data, panel, onPanel, onClose }: Props) {
  const back = () => onPanel(null);
  if (panel === "approach") return <Approach seller={seller} data={data} onBack={back} onClose={onClose} />;
  if (panel === "add") return <AddToDeal seller={seller} data={data} onBack={back} onClose={onClose} />;
  if (panel === "lead") return <NewLead seller={seller} data={data} onClose={onClose} />;
  if (panel === "edit") return <EditProfile seller={seller} data={data} onBack={back} onClose={onClose} />;

  const contacts = seller.contactIds.map((id) => byId(data.people, id)).filter((person) => person !== undefined);
  // Attio links list entries to the organization record; the demo matches names.
  const rows = data.counterparties.filter((row) => row.name === seller.name);
  const listEntry = rows.find((row) => row.listName);
  const dealRows = rows.filter((row) => row.dealId);

  return (
    <Drawer title={seller.name} status={[seller.sector, seller.hq].filter(Boolean).join(", ")} onClose={onClose} actions={<RecordHeaderActions itemName={seller.name} actions={sellerActions(seller).filter((action) => action.panel !== "edit")} onEdit={() => onPanel("edit")} onPick={onPanel} />}>
      <section className="drawer__section">
        <h3 className="panel-heading">Profile</h3>
        <dl className="label-grid label-grid--two">
          <Item label="Open to selling"><OpenToSellingPill value={seller.openToSelling} /></Item>
          <Item label="Owner">{byId(data.users, seller.ownerId)?.name ?? "Not set"}</Item>
          {isLive && <Item label="Company sector">{seller.companySector ?? <span className="muted">Not set</span>}</Item>}
          <Item label="Geography">{seller.geography}</Item>
          <Item label="Revenue">{formatMoney(seller.estRevenueUsd)}</Item>
          <Item label="EBITDA">{formatMoney(seller.estEbitdaUsd)}</Item>
          <Item label="Re-engage">{seller.reEngageDate ? formatDate(seller.reEngageDate) : <span className="muted">Not set</span>}</Item>
          <Item label="Website"><LinkText text={seller.website} /></Item>
        </dl>
        <p className="record-notes">{seller.notes}</p>
      </section>

      <DetailValues fields={data.options.fields.filter((field) => field.key !== "sector_focus")} roleName="Seller" recordId={seller.id} load={() => getSellerDetails(seller.id)} lead={isLive ? [{ label: "Sector (this role)", value: seller.ownSector }] : []} />

      <section className="drawer__section">
        <h3 className="panel-heading">Contacts</h3>
        {contacts.length === 0 ? (
          <p className="muted">No owner contact yet.</p>
        ) : (
          <ul className="plain-list">
            {contacts.map((person, index) => (
              <li key={person.id}>
                <span className="cell-title">{person.name}{index === 0 && <span className="muted"> (owner contact)</span>}</span>
                <span className="cell-sub">{[person.title ?? "Title not set", person.email].filter(Boolean).join(" · ")}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Outreach</h3>
        {listEntry?.outreach ? (
          <p>
            {listEntry.outreach.lastMessage} <span className="muted">Last contact {listEntry.lastContactAt ? formatWhen(listEntry.lastContactAt, data.now) : "not logged"}.</span>
          </p>
        ) : (
          <p className="muted">Not approached yet.</p>
        )}
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Deals</h3>
        {dealRows.length === 0 ? (
          <p className="muted">Not a target on any deal yet.</p>
        ) : (
          <ul className="plain-list">
            {dealRows.map((row) => (
              <li key={row.id} className="buyer-deal">
                <span className="cell-title">{byId(data.deals, row.dealId)?.codeName ?? "Closed deal"}</span>
                <StatusPill status={row.status} />
                <span className="cell-sub">{row.lastContactAt ? `Last contact ${formatWhen(row.lastContactAt, data.now)}` : "Never contacted"}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <EmailLogSection org={seller.name} emails={data.emails} />
    </Drawer>
  );
}

type PanelProps = { seller: SellerRole; data: SellersUniverseData; onBack: () => void; onClose: () => void };

function BackButton({ onBack }: { onBack: () => void }) {
  return (
    <button type="button" className="button button--quiet" onClick={onBack}>
      Back
    </button>
  );
}

// PRD S3 from the universe: a short owner note, sent only on the person's click.
function Approach({ seller, data, onBack, onClose }: PanelProps) {
  const act = useRouteAction(ROUTE);
  const contacts = seller.contactIds.map((id) => byId(data.people, id)).filter((person) => person !== undefined);
  const [contactId, setContactId] = useState(contacts[0]?.id ?? "");
  const contact = byId(data.people, contactId);
  const [body, setBody] = useState(() => ownerApproachBody(contact?.name ?? "", seller.notes));
  const [edited, setEdited] = useState(false);
  const approached = data.counterparties.find((row) => row.listName && row.name === seller.name)?.outreach;
  const blocker = !contact
    ? "No owner contact yet. Find one in Sellers search first."
    : approached
      ? `Already approached on ${formatDate(approached.firstSentAt)}. Follow up from Outreach.`
      : !body.trim()
        ? "Write a message before sending."
        : "";

  const send = () => {
    act({ intent: "approach", id: seller.id, contactId: contact!.id, summary: summaryOf(body) }, `Owner approach sent to ${contact!.name}. Demo: nothing was sent.`);
    onClose();
  };

  return (
    <Drawer
      title={`Ask ${seller.name} if open to selling`}
      dirty={edited}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <>
          <BackButton onBack={onBack} />
          <button type="button" className="button" disabled={Boolean(blocker)} onClick={send}>Send</button>
        </>
      }
    >
      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Message</h3>
          <span className="badge">AI draft</span>
        </div>
        <div className="field">
          <label htmlFor="approach-to">To</label>
          <select
            id="approach-to"
            value={contactId}
            disabled={contacts.length === 0}
            onChange={(event) => {
              setContactId(event.target.value);
              if (!edited) setBody(ownerApproachBody(byId(data.people, event.target.value)?.name ?? "", seller.notes));
            }}
          >
            {contacts.length === 0 && <option value="">No contact yet</option>}
            {contacts.map((person) => (
              <option key={person.id} value={person.id}>{person.name}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="approach-body">Message</label>
          <textarea
            id="approach-body"
            rows={8}
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

function AddToDeal({ seller, data, onBack, onClose }: PanelProps) {
  const act = useRouteAction(ROUTE);
  const onDeal = (dealId: string) => data.counterparties.some((row) => row.dealId === dealId && row.name === seller.name);
  const open = data.deals.filter((deal) => !onDeal(deal.id));
  // Prefilled so the common case is menu, action, Add: 3 clicks.
  const [dealId, setDealId] = useState(open[0]?.id ?? "");
  const deal = byId(data.deals, dealId);
  const blocker = data.deals.length === 0 ? "No active buy-side mandate." : open.length === 0 ? "Already a target on every active buy-side mandate." : "";

  return (
    <Drawer
      title={`Add ${seller.name} to a buy-side deal`}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <>
          <BackButton onBack={onBack} />
          <button
            type="button"
            className="button"
            disabled={Boolean(blocker) || !deal}
            onClick={() => {
              act({ intent: "add-to-deal", id: seller.id, dealId }, `${seller.name} added to ${deal!.codeName} as a target.`);
              onClose();
            }}
          >
            Add
          </button>
        </>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="seller-deal">Deal</label>
          <select id="seller-deal" value={dealId} disabled={open.length === 0} onChange={(event) => setDealId(event.target.value)}>
            {open.map((row) => (
              <option key={row.id} value={row.id}>
                {row.codeName}: {row.clientName}, {row.sector}
              </option>
            ))}
          </select>
        </div>
      </section>
    </Drawer>
  );
}

function NewLead({ seller, data, onClose }: Omit<PanelProps, "onBack">) {
  const act = useRouteAction(ROUTE);
  return (
    <LeadDrawer
      side="sell"
      companyName={seller.name}
      defaults={{ codeName: data.nextCodeName, sector: seller.sector, city: seller.hq }}
      note={seller.notes}
      onClose={onClose}
      onCreate={(fields) => {
        act({ intent: "new-lead", id: seller.id, ...fields }, `${fields.codeName} created as a sell-side lead in the Pipeline.`);
        onClose();
      }}
    />
  );
}

function EditProfile({ seller, data, onBack, onClose }: PanelProps) {
  const { save: send, saving, error } = useSaveAction(ROUTE);
  // The form holds an empty string for no date and leaves the EBITDA undefined when it is blank.
  const initial: Omit<Required<SellerPatch>, "estEbitdaUsd" | "reEngageDate"> & { estEbitdaUsd?: number; reEngageDate: string } = {
    sector: seller.sector,
    geography: seller.geography,
    estRevenueUsd: seller.estRevenueUsd,
    estEbitdaUsd: seller.estEbitdaUsd,
    openToSelling: seller.openToSelling,
    reEngageDate: seller.reEngageDate ?? "",
    ownerId: seller.ownerId,
    notes: seller.notes,
    details: [],
  };
  const [draft, setDraft] = useState(initial);
  // A new seller is the same form with its name, HQ and website first (id "new" until saved).
  const isNew = seller.id === NEW_SELLER.id;
  const [identity, setIdentity] = useState({ name: "", hq: "", website: "" });
  const set = <K extends keyof typeof initial>(key: K, value: (typeof initial)[K]) => setDraft({ ...draft, [key]: value });
  // The sector select already sets a new seller's sector focus, so that field is not offered twice.
  const detailFields = isNew ? data.options.fields.filter((field) => field.key !== "sector_focus") : data.options.fields;
  const details = useDetails(detailFields, isNew ? null : () => getSellerDetails(seller.id));
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial) || details.dirty;
  // Live cannot save these yet. A row's own value is always listed so the select can show it.
  const sectors = [...new Set([...(isNew ? data.options.sectorChoices : data.options.sectors), draft.sector])].filter(Boolean).sort();
  const geographies = [...new Set([...data.options.geographies, draft.geography])].sort();
  const ebitdaTooHigh = draft.estEbitdaUsd !== undefined && draft.estRevenueUsd !== null && draft.estEbitdaUsd > draft.estRevenueUsd;
  const blocker = isNew && (!identity.name.trim() || !identity.website.trim()) ? "Add the seller's name and website." : isNew && !draft.sector ? "Pick a sector." : ebitdaTooHigh ? "EBITDA cannot be above revenue." : details.cleared.length ? `Attio cannot empty ${details.cleared.join(", ")}. Put the value back, or clear it in Attio.` : "";

  const save = () => {
    if (isNew) {
      const added: NewSellerInput = {
        name: identity.name.trim(),
        hq: identity.hq.trim(),
        website: identity.website.trim(),
        sector: draft.sector,
        estRevenueUsd: draft.estRevenueUsd,
        estEbitdaUsd: draft.estEbitdaUsd,
        openToSelling: draft.openToSelling,
        reEngageDate: draft.reEngageDate || undefined,
        details: details.changes,
      };
      send({ intent: "seller-add", seller: JSON.stringify(added) }, `${added.name} added to Attio as a seller role.`, onClose);
      return;
    }
    const changed = changedFields(initial, draft);
    // A missing key means unchanged, so a cleared value goes as null.
    const patch: SellerPatch = {
      ...changed,
      ...("estEbitdaUsd" in changed ? { estEbitdaUsd: changed.estEbitdaUsd ?? null } : {}),
      ...("reEngageDate" in changed ? { reEngageDate: changed.reEngageDate || null } : {}),
      ...(details.changes.length ? { details: details.changes } : {}),
    };
    send({ intent: "seller-update", id: seller.id, patch: JSON.stringify(patch) }, `${seller.name} saved to Attio.`, onBack);
  };

  return (
    <Drawer
      title={isNew ? "Add a seller" : `Edit ${seller.name}`}
      dirty={dirty || Boolean(identity.name)}
      notice={error ?? ((dirty || isNew) && blocker ? blocker : undefined)}
      onClose={onClose}
      actions={
        <>
          {!isNew && <BackButton onBack={onBack} />}
          <button type="button" className="button" disabled={saving || (!dirty && !isNew) || Boolean(blocker)} onClick={save}>Save to Attio</button>
        </>
      }
    >
      <section className="drawer__section">
        <div className="form-grid">
          {isNew && (
            <>
              <div className="field">
                <label htmlFor="seller-name">Name</label>
                <input id="seller-name" value={identity.name} autoFocus onChange={(event) => setIdentity({ ...identity, name: event.target.value })} />
              </div>
              <div className="field">
                {isLive ? (
                  <>
                    <label htmlFor="seller-hq">HQ country</label>
                    <select id="seller-hq" value={identity.hq} onChange={(event) => setIdentity({ ...identity, hq: event.target.value })}>
                      <option value="">Not set</option>
                      {data.options.hqCountries.map((value) => <option key={value}>{value}</option>)}
                    </select>
                  </>
                ) : (
                  <>
                    <label htmlFor="seller-hq">HQ city</label>
                    <input id="seller-hq" value={identity.hq} onChange={(event) => setIdentity({ ...identity, hq: event.target.value })} />
                  </>
                )}
              </div>
              <div className="field">
                <label htmlFor="seller-website">Website</label>
                <input id="seller-website" value={identity.website} placeholder="example.com" onChange={(event) => setIdentity({ ...identity, website: event.target.value })} />
              </div>
            </>
          )}
          <div className="field">
            <label htmlFor="seller-sector">{isLive && !isNew ? "Company sector" : "Sector"}</label>
            {isLive && !isNew ? (
              <input id="seller-sector" value={seller.companySector ?? "Not set"} readOnly disabled />
            ) : (
            <select id="seller-sector" value={draft.sector} disabled={isLive && !isNew} onChange={(event) => set("sector", event.target.value)}>
              {!draft.sector && <option value="">{isNew ? "Pick a sector" : "Not set"}</option>}
              {sectors.map((value) => <option key={value}>{value}</option>)}
            </select>
            )}
          </div>
          {!isNew && (
            <div className="field">
              <label htmlFor="seller-geo">Geography</label>
              <select id="seller-geo" value={draft.geography} disabled={isLive} onChange={(event) => set("geography", event.target.value)}>
                {geographies.map((value) => <option key={value}>{value}</option>)}
              </select>
            </div>
          )}
          <div className="field">
            <label htmlFor="seller-revenue">Revenue (USD)</label>
            <AmountInput id="seller-revenue" value={draft.estRevenueUsd ?? undefined} onChange={(value) => set("estRevenueUsd", value ?? null)} />
          </div>
          <div className="field">
            <label htmlFor="seller-ebitda">EBITDA (USD)</label>
            <AmountInput id="seller-ebitda" value={draft.estEbitdaUsd} onChange={(value) => set("estEbitdaUsd", value)} />
          </div>
          <div className="field">
            <label htmlFor="seller-open">Open to selling</label>
            <select id="seller-open" value={draft.openToSelling} onChange={(event) => set("openToSelling", event.target.value as SellerRole["openToSelling"])}>
              {OPEN_TO_SELLING.map((value) => <option key={value}>{value}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="seller-reengage">Re-engage date</label>
            <input id="seller-reengage" type="date" value={draft.reEngageDate} onChange={(event) => set("reEngageDate", event.target.value)} />
          </div>
          {!isNew && (
            <div className="field">
              <label htmlFor="seller-owner">Owner</label>
              <select id="seller-owner" value={draft.ownerId ?? ""} disabled={isLive} onChange={(event) => set("ownerId", event.target.value)}>
                {draft.ownerId === null && <option value="">Not set</option>}
                {data.users.filter((user) => user.role === "Advisor").map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
              </select>
            </div>
          )}
        </div>
        {!isNew && (
          <div className="field">
            <label htmlFor="seller-notes">Notes</label>
            <textarea id="seller-notes" rows={3} value={draft.notes} disabled={isLive} onChange={(event) => set("notes", event.target.value)} />
          </div>
        )}
      </section>
      <DetailFields fields={detailFields} values={details.values} onChange={details.set} roleName="Seller" status={details.status} lead={isLive && !isNew ? [{ label: "Sector (this role)", value: seller.ownSector ?? "Not set" }] : []} />
    </Drawer>
  );
}
