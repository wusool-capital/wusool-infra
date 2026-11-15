import { useState } from "react";
import type { ClientChoice, NewDealInput } from "../../demo/types";
import { Drawer } from "../ui/drawer";
import { Segmented } from "../ui/segmented";

type Props = { clients: ClientChoice[]; nextCodeName: string; onCreate: (input: NewDealInput) => void; onClose: () => void };

// Typing the client's name searches the roles already in Attio first, so a known company is
// picked rather than added twice. Only when nothing matches does "Add as new" appear.
export function NewDealDrawer({ clients, nextCodeName, onCreate, onClose }: Props) {
  const [side, setSide] = useState<"sell" | "buy">("sell");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<ClientChoice | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [codeName, setCodeName] = useState(nextCodeName);
  const [sector, setSector] = useState("");
  const [city, setCity] = useState("");
  const role = side === "sell" ? "seller role" : "buyer role";

  const term = query.trim().toLowerCase();
  const matches = term ? clients.filter((row) => row.side === side && row.name.toLowerCase().includes(term)).slice(0, 5) : [];
  const chosen = picked || isNew;
  const blocker = !chosen ? "Pick the client or add it as new." : !codeName.trim() || !sector.trim() || !city.trim() ? "Fill in the code name, sector and city." : "";

  const pick = (row: ClientChoice) => {
    setPicked(row);
    setIsNew(false);
    setSector(row.sector);
    setCity(row.city);
  };
  const reset = () => {
    setPicked(null);
    setIsNew(false);
  };

  return (
    <Drawer
      title="New deal"
      dirty={Boolean(query.trim())}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={Boolean(blocker)}
          onClick={() => onCreate({ side, roleId: picked?.id, newName: isNew ? query.trim() : undefined, codeName: codeName.trim(), sector: sector.trim(), city: city.trim() })}
        >
          Create deal
        </button>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <span className="field__label" id="new-deal-side">The client is</span>
          <Segmented role="group" aria-labelledby="new-deal-side">
            {(["sell", "buy"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className="segmented__option"
                aria-pressed={side === value}
                onClick={() => {
                  setSide(value);
                  reset();
                }}
              >
                {value === "sell" ? "Selling (sell-side)" : "Buying (buy-side)"}
              </button>
            ))}
          </Segmented>
        </div>

        <div className="field">
          <label htmlFor="new-deal-client">Client company</label>
          {chosen ? (
            <div className="picked-client">
              <span>
                <span className="cell-title">{picked?.name ?? query.trim()}</span>
                <span className="cell-sub">{picked ? `Already in Attio as a ${role}` : `Will be added to Attio as a new ${role}`}</span>
              </span>
              <button type="button" className="button button--small button--quiet" onClick={reset}>
                Change
              </button>
            </div>
          ) : (
            <>
              <input id="new-deal-client" value={query} autoFocus placeholder={`Search ${role}s in Attio`} onChange={(event) => setQuery(event.target.value)} />
              {term && (
                <ul className="client-matches">
                  {matches.map((row) => (
                    <li key={row.id}>
                      <button type="button" className="client-matches__option" onClick={() => pick(row)}>
                        <span className="cell-title">{row.name}</span>
                        <span className="cell-sub">
                          {row.sector}, {row.city}
                        </span>
                      </button>
                    </li>
                  ))}
                  <li>
                    <button type="button" className="client-matches__option client-matches__option--new" onClick={() => setIsNew(true)}>
                      Add "{query.trim()}" as a new {role}
                    </button>
                  </li>
                </ul>
              )}
            </>
          )}
        </div>

        <div className="form-grid">
          <div className="field">
            <label htmlFor="new-deal-code">Code name</label>
            <input id="new-deal-code" value={codeName} onChange={(event) => setCodeName(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="new-deal-sector">{side === "buy" ? "Target sector" : "Sector"}</label>
            <input id="new-deal-sector" value={sector} onChange={(event) => setSector(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="new-deal-city">City</label>
            <input id="new-deal-city" value={city} onChange={(event) => setCity(event.target.value)} />
          </div>
        </div>
      </section>
    </Drawer>
  );
}
