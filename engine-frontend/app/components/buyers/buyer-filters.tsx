import type { ReactNode } from "react";
import { BUYER_TYPES } from "../../demo/types";
import type { BuyerProfile } from "../../lib/buyer-filters";
import type { FilterDef } from "../../lib/filters";
import { FilterBar } from "../ui/filter-bar";

const sorted = (values: string[]) => [...new Set(values)].sort();

export function BuyerFilters({ buyers, before, children, shown, alsoClear }: { buyers: BuyerProfile[]; before?: ReactNode; children: ReactNode; shown?: number; alsoClear?: string[] }) {
  const filters: FilterDef[] = [
    { kind: "list", key: "sector", label: "Sector", options: sorted(buyers.flatMap((b) => b.sectors)) },
    { kind: "list", key: "geography", label: "Geography", options: sorted(buyers.flatMap((b) => b.geographies)) },
    { kind: "list", key: "type", label: "Type", options: [...BUYER_TYPES] },
    { kind: "range", key: "checkSize", label: "Check size" },
    { kind: "range", key: "minEbitda", label: "Min. EBITDA" },
  ];
  return (
    <FilterBar before={before} filters={filters} shown={shown} total={shown === undefined ? undefined : buyers.length} alsoClear={alsoClear}>
      {children}
    </FilterBar>
  );
}
