import { NavLink } from "react-router";
import { lastUrlAt } from "../../lib/page-memory";
import { Segmented } from "./segmented";

// One Search page for both sides: each side keeps its own route (loader, actions),
// the switch only moves between them, back to each side's last filters and results.
export function SearchSwitch() {
  return (
    <Segmented as="nav" aria-label="Search for">
      <NavLink to={lastUrlAt("/search/buyers")} className="segmented__option">
        Buyers
      </NavLink>
      <NavLink to={lastUrlAt("/search/sellers")} className="segmented__option">
        Sellers
      </NavLink>
    </Segmented>
  );
}
