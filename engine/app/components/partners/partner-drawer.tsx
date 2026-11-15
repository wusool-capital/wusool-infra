import { useState } from "react";
import type { Partner, PartnerPublic, PartnerTerms, PartnersData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatDate, formatWhen } from "../../lib/format";
import { LeadDrawer } from "../pipeline/lead-drawer";
import { Drawer } from "../ui/drawer";
import { LabelItem as Item, RecordHeaderActions } from "../ui/record-parts";
import { useRouteAction } from "../ui/toast";

export const PARTNER_ACTIONS = [
  { panel: "lead", label: "New referred lead" },
  { panel: "edit", label: "Edit and publish" },
] as const;
export type PartnerPanel = (typeof PARTNER_ACTIONS)[number]["panel"];
const DRAWER_MENU = PARTNER_ACTIONS.filter((action) => action.panel !== "edit");
const ROUTE = "/partners";

type Props = { partner: Partner; data: PartnersData; panel: PartnerPanel | null; onPanel: (panel: PartnerPanel | null) => void; onClose: () => void };

// PRD PA1 to PA3: the public profile, internal terms behind Show terms (they are fees), and
// the leads this partner referred. Edit replaces the content in place, so the page keeps one layer.
/** The empty partner behind "Add partner". */
export const NEW_PARTNER: Partner = {
  id: "new",
  order: 0,
  publishedAt: "",
  name: "",
  category: "",
  description: "",
  offer: "",
  referralType: "Code",
  referral: "",
  url: "",
  locations: [],
  companySizes: [],
  active: false,
  terms: { commission: "", agreement: "", contactName: "", contactEmail: "" },
};

export function PartnerDrawer({ partner, data, panel, onPanel, onClose }: Props) {
  const [showTerms, setShowTerms] = useState(false);
  if (panel === "edit") return <EditPartner partner={partner} onBack={() => onPanel(null)} onClose={onClose} />;
  if (panel === "lead") return <ReferredLead partner={partner} data={data} onClose={onClose} />;

  const leads = data.deals.filter((deal) => deal.sourcePartnerId === partner.id);

  return (
    <Drawer
      title={partner.name}
      status={`${partner.category}. ${partner.active ? "Active, listed on the website" : "Inactive, not on the website"}, last published ${formatDate(partner.publishedAt)}`}
      onClose={onClose}
      actions={<RecordHeaderActions itemName={partner.name} actions={DRAWER_MENU} onEdit={() => onPanel("edit")} onPick={onPanel} />}
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Website profile</h3>
        <dl className="label-grid label-grid--two">
          <Item label="Offer">{partner.offer}</Item>
          <Item label={`Referral ${partner.referralType.toLowerCase()}`}>{partner.referral}</Item>
          <Item label="Website">{partner.url}</Item>
          <Item label="Locations">{partner.locations.join(", ")}</Item>
          <Item label="Company sizes">{partner.companySizes.join(", ")}</Item>
        </dl>
        <p className="record-notes">{partner.description}</p>
      </section>

      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Internal terms</h3>
          <button type="button" className="button button--small button--quiet" onClick={() => setShowTerms(!showTerms)}>
            {showTerms ? "Hide terms" : "Show terms"}
          </button>
        </div>
        {showTerms && (
          <dl className="label-grid label-grid--two">
            <Item label="Commission">{partner.terms.commission}</Item>
            <Item label="Agreement">{partner.terms.agreement}</Item>
            <Item label="Contact">{`${partner.terms.contactName}, ${partner.terms.contactEmail}`}</Item>
          </dl>
        )}
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Leads referred</h3>
        {leads.length === 0 ? (
          <p className="muted">No leads from this partner yet.</p>
        ) : (
          <ul className="plain-list">
            {leads.map((deal) => (
              <li key={deal.id} className="buyer-deal">
                <span className="cell-title">
                  {deal.codeName} <span className="muted">({deal.clientName})</span>
                </span>
                <span className="chip">{deal.status === "Active" ? deal.stage : deal.status}</span>
                <span className="cell-sub">
                  Owner {byId(data.users, deal.ownerId)?.name}. Last activity {formatWhen(deal.lastActivityAt, data.now)}. Next: {deal.nextStep}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Drawer>
  );
}

const SIZES = ["Under $5M revenue", "$5M to $20M revenue", "Over $20M revenue"];

// PRD PA2: the website changes only on Publish, after a preview of the public card.
function EditPartner({ partner, onBack, onClose }: { partner: Partner; onBack: () => void; onClose: () => void }) {
  const act = useRouteAction(ROUTE);
  const initial: PartnerPublic = {
    name: partner.name,
    category: partner.category,
    description: partner.description,
    offer: partner.offer,
    referralType: partner.referralType,
    referral: partner.referral,
    url: partner.url,
    locations: partner.locations,
    companySizes: partner.companySizes,
    active: partner.active,
  };
  const [draft, setDraft] = useState(initial);
  const [terms, setTerms] = useState<PartnerTerms>(partner.terms);
  const set = <K extends keyof PartnerPublic>(key: K, value: PartnerPublic[K]) => setDraft({ ...draft, [key]: value });
  const dirty = JSON.stringify([draft, terms]) !== JSON.stringify([initial, partner.terms]);
  // A new partner is the same form with its name and category first (id "new" until saved).
  const isNew = partner.id === NEW_PARTNER.id;
  const blocker =
    isNew && (!draft.name.trim() || !draft.category.trim())
      ? "Add the partner's name and category."
      : !draft.offer.trim() || !draft.referral.trim()
        ? "The offer and the referral are shown on the website. Fill both."
        : "";

  return (
    <Drawer
      title={isNew ? "Add a referral partner" : `Edit ${partner.name}`}
      dirty={dirty}
      notice={dirty && blocker ? blocker : undefined}
      onClose={onClose}
      actions={
        <>
          {!isNew && <button type="button" className="button button--quiet" onClick={onBack}>Back</button>}
          <button
            type="button"
            className="button"
            disabled={!dirty || Boolean(blocker)}
            onClick={() => {
              act({ intent: "publish", id: partner.id, fields: JSON.stringify(draft), terms: JSON.stringify(terms) }, `${draft.name} ${draft.active ? "published to the website" : "saved, not on the website"}.`);
              onBack();
            }}
          >
            Publish to website
          </button>
        </>
      }
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Website profile</h3>
        <div className="form-grid">
          {isNew && (
            <>
              <div className="field">
                <label htmlFor="pa-name">Name</label>
                <input id="pa-name" value={draft.name} autoFocus onChange={(event) => set("name", event.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="pa-category">Category</label>
                <input id="pa-category" value={draft.category} placeholder="e.g. Accounting" onChange={(event) => set("category", event.target.value)} />
              </div>
            </>
          )}
          <div className="field">
            <label htmlFor="pa-offer">Offer</label>
            <input id="pa-offer" value={draft.offer} onChange={(event) => set("offer", event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pa-url">Website</label>
            <input id="pa-url" value={draft.url} onChange={(event) => set("url", event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pa-ref-type">Referral type</label>
            <select id="pa-ref-type" value={draft.referralType} onChange={(event) => set("referralType", event.target.value as PartnerPublic["referralType"])}>
              <option>Code</option>
              <option>Link</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="pa-ref">Referral {draft.referralType.toLowerCase()}</label>
            <input id="pa-ref" value={draft.referral} onChange={(event) => set("referral", event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pa-locations">Locations (comma separated)</label>
            <input id="pa-locations" value={draft.locations.join(", ")} onChange={(event) => set("locations", event.target.value.split(",").map((value) => value.trim()).filter(Boolean))} />
          </div>
          <div className="field">
            <label htmlFor="pa-active">On the website</label>
            <select id="pa-active" value={draft.active ? "yes" : "no"} onChange={(event) => set("active", event.target.value === "yes")}>
              <option value="yes">Active, listed</option>
              <option value="no">Inactive, not listed</option>
            </select>
          </div>
        </div>
        <fieldset className="check-group">
          <legend>Company sizes</legend>
          {SIZES.map((size) => (
            <label key={size} className="check-group__option">
              <input
                type="checkbox"
                checked={draft.companySizes.includes(size)}
                onChange={() => set("companySizes", draft.companySizes.includes(size) ? draft.companySizes.filter((item) => item !== size) : [...draft.companySizes, size])}
              />
              {size}
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor="pa-description">Description</label>
          <textarea id="pa-description" rows={3} value={draft.description} onChange={(event) => set("description", event.target.value)} />
        </div>
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Preview on the website</h3>
        <div className="partner-preview">
          <p className="partner-preview__category">{draft.category}</p>
          <p className="partner-preview__name">{draft.name}</p>
          <p>{draft.description}</p>
          <p className="partner-preview__offer">{draft.offer}</p>
          <p className="muted">
            {draft.referralType === "Code" ? `Use code ${draft.referral}` : draft.referral}. {draft.locations.join(", ")}.
          </p>
          {!draft.active && <p className="field-error">Hidden: this card will not appear on the website.</p>}
        </div>
      </section>

      <section className="drawer__section">
        <h3 className="panel-heading">Internal terms</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="pa-commission">Commission</label>
            <input id="pa-commission" value={terms.commission} onChange={(event) => setTerms({ ...terms, commission: event.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="pa-agreement">Agreement</label>
            <input id="pa-agreement" value={terms.agreement} onChange={(event) => setTerms({ ...terms, agreement: event.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="pa-contact">Contact name</label>
            <input id="pa-contact" value={terms.contactName} onChange={(event) => setTerms({ ...terms, contactName: event.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="pa-email">Contact email</label>
            <input id="pa-email" value={terms.contactEmail} onChange={(event) => setTerms({ ...terms, contactEmail: event.target.value })} />
          </div>
        </div>
      </section>
    </Drawer>
  );
}

// Most partners (accountants, lawyers) refer owners, so a referred lead starts sell-side.
function ReferredLead({ partner, data, onClose }: { partner: Partner; data: PartnersData; onClose: () => void }) {
  const act = useRouteAction(ROUTE);
  return (
    <LeadDrawer
      side="sell"
      companyName=""
      defaults={{ codeName: data.nextCodeName, sector: "", city: partner.locations[0] === "UAE" ? "Dubai" : "" }}
      note={`Source: ${partner.name}. The lead counts toward this partner's referrals.`}
      onClose={onClose}
      onCreate={(fields) => {
        act({ intent: "lead", id: partner.id, ...fields }, `${fields.codeName} created in the Pipeline, referred by ${partner.name}.`);
        onClose();
      }}
    />
  );
}
