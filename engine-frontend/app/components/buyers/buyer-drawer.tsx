import { useState } from "react";
import { BUYER_TYPES, type BuyerPatch, type BuyerRole, type BuyersUniverseData, type DetailValue } from "../../demo/types";
import { getBuyerDetails } from "../../api";
import { changedFields } from "../../lib/action-result";
import { byId } from "../../lib/by-id";
import { isLive } from "../../lib/data-mode";
import { useDetails } from "../../lib/use-details";
import { formatMoney, formatMoneyRange, formatWhen } from "../../lib/format";
import { StatusPill } from "../mandates/status-pill";
import { AmountInput } from "../ui/amount-input";
import { CheckGroup } from "../ui/check-group";
import { DetailFields } from "../ui/detail-fields";
import { DetailValues } from "../ui/detail-values";
import { Drawer } from "../ui/drawer";
import { LinkText } from "../ui/link-text";
import { useRouteAction, useSaveAction } from "../ui/toast";
import { EmailLogSection, LabelItem as Item, RecordHeaderActions } from "../ui/record-parts";
import { BuyerStatusPill } from "./buyer-status-pill";

/** Row menu actions; the drawer shows Edit as its own button. Live greys out Add to a deal until mandates. */
export const BUYER_ACTIONS = [
  { panel: "add", label: "Add to a deal", disabled: isLive },
  { panel: "edit", label: "Edit profile" },
] as const;
export type BuyerPanel = (typeof BUYER_ACTIONS)[number]["panel"];
const DRAWER_MENU = BUYER_ACTIONS.filter((action) => action.panel !== "edit");

type Props = {
  buyer: BuyerRole;
  data: BuyersUniverseData;
  panel: BuyerPanel | null;
  onPanel: (panel: BuyerPanel | null) => void;
  onClose: () => void;
};

// PRD U1: the record drawer is read only. Add to a deal and Edit profile replace its
// content in place, so the page keeps one layer.
/** The empty buyer behind "Add buyer". */
export const NEW_BUYER: BuyerRole = {
  id: "new",
  name: "",
  type: isLive ? null : "Strategic",
  hq: "",
  website: "",
  sectors: [],
  geographies: [],
  checkSizeMinUsd: isLive ? null : 0,
  checkSizeMaxUsd: isLive ? null : 0,
  ebitdaFloorUsd: isLive ? null : 0,
  ownerId: "jules",
  status: "Active",
  contactIds: [],
  notes: "",
};

export function BuyerDrawer({ buyer, data, panel, onPanel, onClose }: Props) {
  if (panel === "add") return <AddToDeal buyer={buyer} data={data} onBack={() => onPanel(null)} onClose={onClose} />;
  if (panel === "edit") return <EditProfile buyer={buyer} data={data} onBack={() => onPanel(null)} onClose={onClose} />;

  const contacts = buyer.contactIds.map((id) => byId(data.people, id)).filter((person) => person !== undefined);
  // Attio links counterparties to the organization record; the demo matches names.
  const dealRows = data.counterparties.filter((row) => row.name === buyer.name);
  const owner = byId(data.users, buyer.ownerId);

  return (
    <Drawer title={buyer.name} status={[buyer.type, buyer.hq].filter(Boolean).join(", ")} onClose={onClose} actions={<RecordHeaderActions itemName={buyer.name} actions={DRAWER_MENU} onEdit={() => onPanel("edit")} onPick={onPanel} />}>
      <section className="drawer__section">
        <h3 className="panel-heading">Profile</h3>
        <dl className="label-grid label-grid--two">
          <Item label="Status"><BuyerStatusPill status={buyer.status} /></Item>
          <Item label="Owner">{owner?.name ?? "Not set"}</Item>
          {isLive ? <Item label="Company sector">{buyer.companySector ?? <span className="muted">Not set</span>}</Item> : <Item label="Sectors">{buyer.sectors.join(", ")}</Item>}
          <Item label="Target geography">{buyer.geographies.join(", ")}</Item>
          <Item label="Check size">{checkSizeLabel(buyer)}</Item>
          <Item label="Min. EBITDA">{formatMoney(buyer.ebitdaFloorUsd)}</Item>
          <Item label="Website"><LinkText text={buyer.website} /></Item>
        </dl>
        <p className="record-notes">{buyer.notes}</p>
      </section>

      <DetailValues fields={data.options.fields.filter((field) => field.key !== "sector_focus")} roleName="Buyer" recordId={buyer.id} load={() => getBuyerDetails(buyer.id)} lead={isLive ? [{ label: "Target vertical", value: buyer.sectors.join(", ") }] : []} />

      <section className="drawer__section">
        <h3 className="panel-heading">Contacts</h3>
        {contacts.length === 0 ? (
          <p className="muted">No contact yet.</p>
        ) : (
          <ul className="plain-list">
            {contacts.map((person, index) => (
              <li key={person.id}>
                <span className="cell-title">{person.name}{index === 0 && <span className="muted"> (key contact)</span>}</span>
                <span className="cell-sub">{[person.title ?? "Title not set", person.email].filter(Boolean).join(" · ")}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Deals</h3>
        {dealRows.length === 0 ? (
          <p className="muted">Not on any deal yet.</p>
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

      <EmailLogSection org={buyer.name} emails={data.emails} />
    </Drawer>
  );
}

export function checkSizeLabel(buyer: Pick<BuyerRole, "checkSizeMinUsd" | "checkSizeMaxUsd">) {
  return formatMoneyRange(buyer.checkSizeMinUsd, buyer.checkSizeMaxUsd);
}

type PanelProps = { buyer: BuyerRole; data: BuyersUniverseData; onBack: () => void; onClose: () => void };

function AddToDeal({ buyer, data, onBack, onClose }: PanelProps) {
  const act = useRouteAction("/buyers/universe");
  const onDeal = (dealId: string) => data.counterparties.some((row) => row.dealId === dealId && row.name === buyer.name);
  const open = data.deals.filter((deal) => !onDeal(deal.id));
  // Prefilled so the common case is menu, Add to a deal, Add: 3 clicks.
  const [dealId, setDealId] = useState(open[0]?.id ?? "");
  const deal = byId(data.deals, dealId);
  const blocker = buyer.status === "Do not contact" ? "Marked do not contact. Change the status in Edit profile first." : open.length === 0 ? "Already on every active sell-side mandate." : "";

  const add = () => {
    act({ intent: "add-to-deal", id: buyer.id, dealId }, `${buyer.name} added to ${deal!.codeName} as not contacted.`);
    onClose();
  };

  return (
    <Drawer
      title={`Add ${buyer.name} to a deal`}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="button button--quiet" onClick={onBack}>Back</button>
          <button type="button" className="button" disabled={Boolean(blocker) || !deal} onClick={add}>Add</button>
        </>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="buyer-deal">Deal</label>
          <select id="buyer-deal" value={dealId} disabled={open.length === 0} onChange={(event) => setDealId(event.target.value)}>
            {open.map((row) => (
              <option key={row.id} value={row.id}>
                {row.codeName}: {row.sector}, {row.city}
              </option>
            ))}
          </select>
        </div>
        {data.deals.filter((row) => onDeal(row.id)).length > 0 && (
          <p className="muted">Already on {data.deals.filter((row) => onDeal(row.id)).map((row) => row.codeName).join(", ")}.</p>
        )}
      </section>
    </Drawer>
  );
}

function EditProfile({ buyer, data, onBack, onClose }: PanelProps) {
  const { save: send, saving, error } = useSaveAction("/buyers/universe");
  const initial: Required<BuyerPatch> = {
    type: buyer.type,
    status: buyer.status,
    ownerId: buyer.ownerId,
    sectors: buyer.sectors,
    geographies: buyer.geographies,
    checkSizeMinUsd: buyer.checkSizeMinUsd,
    checkSizeMaxUsd: buyer.checkSizeMaxUsd,
    ebitdaFloorUsd: buyer.ebitdaFloorUsd,
    notes: buyer.notes,
    hq: buyer.hq,
    details: [],
  };
  const [draft, setDraft] = useState(initial);
  // A new buyer is the same form with its name, HQ and website first (id "new" until saved).
  const isNew = buyer.id === NEW_BUYER.id;
  const [identity, setIdentity] = useState({ name: "", hq: "", website: "" });
  const set = <K extends keyof BuyerPatch>(key: K, value: Required<BuyerPatch>[K]) => setDraft({ ...draft, [key]: value });
  const toggle = <T extends string>(list: T[], value: T) => (list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  // The extra Slack fields load with the record; a new buyer starts with none.
  const details = useDetails(data.options.fields, isNew ? null : () => getBuyerDetails(buyer.id));
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial) || details.dirty;

  // Live has no source for type or owner yet; a new buyer's sector is what Attio files it under.
  const sectorsLocked = isLive && !isNew;
  // The company's sector is edited here, so the same field is left out of Company details below.
  const companySectors = sectorsLocked ? data.options.fields.find((field) => field.key === "sector_focus") : undefined;
  const asList = (value: DetailValue | undefined) => (Array.isArray(value) ? value : []);
  // Attio holds one sector per buyer role, so a live new buyer takes exactly one.
  const oneSector = isLive && isNew;
  const bothSizes = draft.checkSizeMinUsd !== null && draft.checkSizeMaxUsd !== null;
  const blocker =
    isNew && (!identity.name.trim() || !identity.hq.trim()) ? isLive ? "Add the buyer's name and HQ country." : "Add the buyer's name and HQ." : !draft.sectors.length ? "Pick at least one sector." : !isLive && !draft.geographies.length ? "Pick at least one geography." : bothSizes && draft.checkSizeMinUsd! > draft.checkSizeMaxUsd! ? "Check size from must be lower than check size to." : details.cleared.length ? `Attio cannot empty ${details.cleared.join(", ")}. Put the value back, or clear it in Attio.` : "";

  const save = () => {
    if (isNew) {
      const added = { ...draft, details: details.changes, name: identity.name.trim(), hq: identity.hq.trim(), website: identity.website.trim() };
      send({ intent: "buyer-add", buyer: JSON.stringify(added) }, `${added.name} added to Attio as a buyer role.`, onClose);
      return;
    }
    send({ intent: "buyer-update", id: buyer.id, patch: JSON.stringify({ ...changedFields(initial, draft), ...(details.changes.length ? { details: details.changes } : {}) }) }, `${buyer.name} saved to Attio.`, onBack);
  };

  return (
    <Drawer
      title={isNew ? "Add a buyer" : `Edit ${buyer.name}`}
      dirty={dirty || Boolean(identity.name)}
      notice={error ?? (dirty && blocker ? blocker : undefined)}
      onClose={onClose}
      actions={
        <>
          {!isNew && <button type="button" className="button button--quiet" onClick={onBack}>Back</button>}
          <button type="button" className="button" disabled={saving || (!dirty && !isNew) || Boolean(blocker)} onClick={save}>Save to Attio</button>
        </>
      }
    >
      <DetailFields
        fields={sectorsLocked ? data.options.fields.filter((field) => field.key !== "sector_focus") : data.options.fields}
        values={details.values}
        onChange={details.set}
        roleName="Buyer"
        status={details.status}
        companyFirst={isNew}
        role={
          <>
            <div className="form-grid">
              {sectorsLocked && (
                <div className="field">
                  <label htmlFor="buyer-target-vertical">Target vertical</label>
                  <input id="buyer-target-vertical" value={buyer.sectors.join(", ") || "Not set"} readOnly disabled />
                </div>
              )}
              <div className="field">
                <label htmlFor="buyer-status">Status</label>
                <select id="buyer-status" value={draft.status ?? ""} onChange={(event) => set("status", event.target.value)}>
                  {draft.status === null && <option value="">Not set</option>}
                  {data.options.statuses.map((value) => <option key={value}>{value}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="buyer-ebitda-floor">Min. EBITDA (USD)</label>
                <AmountInput id="buyer-ebitda-floor" value={draft.ebitdaFloorUsd ?? undefined} onChange={(value) => set("ebitdaFloorUsd", value ?? null)} />
              </div>
              <div className="field">
                <label htmlFor="buyer-ticket-min">Check size from (USD)</label>
                <AmountInput id="buyer-ticket-min" value={draft.checkSizeMinUsd ?? undefined} onChange={(value) => set("checkSizeMinUsd", value ?? null)} />
              </div>
              <div className="field">
                <label htmlFor="buyer-ticket-max">Check size to (USD)</label>
                <AmountInput id="buyer-ticket-max" value={draft.checkSizeMaxUsd ?? undefined} onChange={(value) => set("checkSizeMaxUsd", value ?? null)} />
              </div>
            </div>
            {!sectorsLocked && (
              <CheckGroup
                legend={oneSector ? "Sector (one per buyer)" : "Sectors"}
                options={data.options.sectorChoices ?? data.options.sectors}
                picked={draft.sectors}
                onToggle={(value) => set("sectors", oneSector ? (draft.sectors.includes(value) ? [] : [value]) : toggle(draft.sectors, value))}
              />
            )}
            <CheckGroup legend="Target geography" options={data.options.geographyChoices} picked={draft.geographies} onToggle={(value) => set("geographies", toggle(draft.geographies, value))} />
            <div className="field">
              <label htmlFor="buyer-notes">Notes</label>
              <textarea id="buyer-notes" rows={3} value={draft.notes} onChange={(event) => set("notes", event.target.value)} />
            </div>
            {sectorsLocked && <p className="muted">A buyer role has one target vertical. To cover another, use Add buyer with the same website to create a new role for it.</p>}
          </>
        }
        company={
          <>
            <div className="form-grid">
              {isNew && (
                <>
                  <div className="field">
                    <label htmlFor="buyer-name">Name</label>
                    <input id="buyer-name" value={identity.name} autoFocus onChange={(event) => setIdentity({ ...identity, name: event.target.value })} />
                  </div>
                  <div className="field">
                    {isLive ? (
                      <>
                        <label htmlFor="buyer-hq">HQ country</label>
                        <select id="buyer-hq" value={identity.hq} onChange={(event) => setIdentity({ ...identity, hq: event.target.value })}>
                          <option value="">Pick a country</option>
                          {data.options.hqCountries.map((value) => <option key={value}>{value}</option>)}
                        </select>
                      </>
                    ) : (
                      <>
                        <label htmlFor="buyer-hq">HQ city</label>
                        <input id="buyer-hq" value={identity.hq} onChange={(event) => setIdentity({ ...identity, hq: event.target.value })} />
                      </>
                    )}
                  </div>
                  <div className="field">
                    <label htmlFor="buyer-website">Website</label>
                    <input id="buyer-website" value={identity.website} placeholder="example.com" onChange={(event) => setIdentity({ ...identity, website: event.target.value })} />
                  </div>
                </>
              )}
              {isLive && !isNew && (
                <div className="field">
                  <label htmlFor="buyer-hq-edit">HQ country</label>
                  <select id="buyer-hq-edit" value={draft.hq} onChange={(event) => set("hq", event.target.value)}>
                    {!draft.hq && <option value="">Not set</option>}
                    {[...new Set([draft.hq, ...data.options.hqCountries].filter(Boolean))].map((value) => <option key={value}>{value}</option>)}
                  </select>
                </div>
              )}
              {!isLive && (
                <div className="field">
                  <label htmlFor="buyer-type">Type</label>
                  <select id="buyer-type" value={draft.type ?? ""} onChange={(event) => set("type", event.target.value as BuyerRole["type"])}>
                    {draft.type === null && <option value="">Not set</option>}
                    {BUYER_TYPES.map((value) => <option key={value}>{value}</option>)}
                  </select>
                </div>
              )}
              <div className="field">
                <label htmlFor="buyer-owner">Owner</label>
                <select id="buyer-owner" value={draft.ownerId ?? ""} disabled={isLive} onChange={(event) => set("ownerId", event.target.value)}>
                  {draft.ownerId === null && <option value="">Not set</option>}
                  {data.users.filter((user) => user.role === "Advisor").map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
                </select>
              </div>
            </div>
            {companySectors && (details.status === "ready" ? (
              <CheckGroup
                legend="Company sector"
                options={companySectors.options}
                picked={asList(details.values.sector_focus)}
                onToggle={(option) => details.set("sector_focus", toggle(asList(details.values.sector_focus), option))}
              />
            ) : (
              <p className="muted">Loading the company sector…</p>
            ))}
          </>
        }
      />
    </Drawer>
  );
}
