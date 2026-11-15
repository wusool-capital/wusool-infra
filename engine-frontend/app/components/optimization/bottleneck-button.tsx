import { useState } from "react";
import { navItems } from "../../lib/nav";
import { Drawer } from "../ui/drawer";
import { useRouteAction } from "../ui/toast";

type DealName = { id: string; codeName: string };

// PRD EO2: 2 clicks (this button, then Save), from the top of Engine optimization (moved from the nav, 8 Nov 2026).
export function BottleneckButton({ deals }: { deals: DealName[] }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="button" onClick={() => setOpen(true)}>
        Log bottleneck
      </button>
      {open && <BottleneckDrawer deals={deals} onClose={() => setOpen(false)} />}
    </>
  );
}

function BottleneckDrawer({ deals, onClose }: { deals: DealName[]; onClose: () => void }) {
  const act = useRouteAction("/optimization");
  const places = ["Deal view", ...navItems.filter((item) => !item.external).map((item) => item.title)];
  const [what, setWhat] = useState("");
  const [where, setWhere] = useState(places[0]);
  const [dealId, setDealId] = useState("");

  return (
    <Drawer
      title="Log a bottleneck"
      dirty={Boolean(what.trim())}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={!what.trim()}
          onClick={() => {
            act({ intent: "log-bottleneck", what: what.trim(), where, dealId }, "Bottleneck logged in Engine optimization.");
            onClose();
          }}
        >
          Save
        </button>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="bn-what">What broke or slowed you down</label>
          <textarea id="bn-what" rows={4} value={what} autoFocus onChange={(event) => setWhat(event.target.value)} />
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="bn-where">Where</label>
            <select id="bn-where" value={where} onChange={(event) => setWhere(event.target.value)}>
              {places.map((place) => (
                <option key={place}>{place}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="bn-deal">Deal</label>
            <select id="bn-deal" value={dealId} onChange={(event) => setDealId(event.target.value)}>
              <option value="">No deal</option>
              {deals.map((deal) => (
                <option key={deal.id} value={deal.id}>
                  {deal.codeName}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
    </Drawer>
  );
}
