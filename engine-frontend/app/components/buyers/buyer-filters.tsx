import type { ReactNode } from "react";
import { BUYER_TYPES } from "../../demo/types";
import type { BuyerProfile } from "../../lib/buyer-filters";
import type { FilterDef } from "../../lib/filters";
import { FilterBar } from "../ui/filter-bar";

const sorted = (values: string[]) => [...new Set(values)].sort();

type Props = {
  /** Rows to take the sector and geography choices from; a paged list passes `options` and `total` instead. */
  buyers?: BuyerProfile[];
  options?: { sectors: string[]; geographies: string[] };
  total?: number;
  /** Live has no source for the type yet, so it passes none and the filter is left out. */
  types?: readonly string[];
  before?: ReactNode;
  children: ReactNode;
  shown?: number;
  alsoClear?: string[];
};

export function BuyerFilters({ buyers = [], options, total, types = BUYER_TYPES, before, children, shown, alsoClear }: Props) {
  const filters: FilterDef[] = [
    { kind: "list", key: "sector", label: "Sector", options: options?.sectors ?? sorted(buyers.flatMap((b) => b.sectors)) },
    { kind: "list", key: "geography", label: "Geography", options: options?.geographies ?? sorted(buyers.flatMap((b) => b.geographies)) },
    ...(types.length ? [{ kind: "list" as const, key: "type", label: "Type", options: [...types] }] : []),
    { kind: "range", key: "checkSize", label: "Check size" },
    { kind: "range", key: "minEbitda", label: "Min. EBITDA" },
  ];
  return (
    <FilterBar before={before} filters={filters} shown={shown} total={shown === undefined ? undefined : (total ?? buyers.length)} alsoClear={alsoClear}>
      {children}
    </FilterBar>
  );
}
