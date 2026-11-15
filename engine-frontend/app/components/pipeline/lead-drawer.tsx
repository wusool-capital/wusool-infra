import { useState } from "react";
import { Drawer } from "../ui/drawer";

export type LeadFields = { codeName: string; sector: string; city: string; clientName: string };

type Props = {
  side: "buy" | "sell";
  /** Empty when the client is not known yet (a partner referral): a Client field appears. */
  companyName: string;
  defaults: Omit<LeadFields, "clientName">;
  note: string;
  onCreate: (fields: LeadFields) => void;
  onClose: () => void;
};

// From Buyers search a buyer becomes a buy-side lead; from the Sellers universe an owner
// becomes a sell-side lead. Either way the deal starts at Lead in the Pipeline.
export function LeadDrawer({ side, companyName, defaults, note, onCreate, onClose }: Props) {
  const [codeName, setCodeName] = useState(defaults.codeName);
  const [sector, setSector] = useState(defaults.sector);
  const [city, setCity] = useState(defaults.city);
  const [clientName, setClientName] = useState(companyName);
  const blocker = !clientName.trim() || !codeName.trim() || !sector.trim() || !city.trim() ? "Fill in the client, code name, sector and city." : "";

  return (
    <Drawer
      title={companyName ? `New ${side}-side lead: ${companyName}` : `New ${side}-side lead`}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <button type="button" className="button" disabled={Boolean(blocker)} onClick={() => onCreate({ codeName: codeName.trim(), sector: sector.trim(), city: city.trim(), clientName: clientName.trim() })}>
          Create lead
        </button>
      }
    >
      <section className="drawer__section">
        <div className="form-grid">
          {!companyName && (
            <div className="field">
              <label htmlFor="lead-client">Client</label>
              <input id="lead-client" value={clientName} autoFocus onChange={(event) => setClientName(event.target.value)} />
            </div>
          )}
          <div className="field">
            <label htmlFor="lead-code">Code name</label>
            <input id="lead-code" value={codeName} onChange={(event) => setCodeName(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="lead-sector">{side === "buy" ? "Target sector" : "Sector"}</label>
            <input id="lead-sector" value={sector} onChange={(event) => setSector(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="lead-city">City</label>
            <input id="lead-city" value={city} onChange={(event) => setCity(event.target.value)} />
          </div>
        </div>
        <p className="muted">{note}</p>
      </section>
    </Drawer>
  );
}
