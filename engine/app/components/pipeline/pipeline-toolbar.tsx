import { useSearchParams } from "react-router";
import { DEAL_STATUSES, type User, type UserId } from "../../demo/types";
import { readList } from "../../lib/filters";
import { FilterBar } from "../ui/filter-bar";
import { TextSearch } from "../ui/text-search";
import { Segmented } from "../ui/segmented";

export type PipelineFilters = { view: "board" | "list"; sides: string[]; owners: string[]; statuses: string[] };

/** Filters live in the URL so a filtered view can be shared or bookmarked. Defaults: my active deals. */
export function readFilters(params: URLSearchParams, currentUserId: UserId): PipelineFilters {
  return {
    view: params.get("view") === "list" ? "list" : "board",
    sides: readList(params, "side"),
    owners: readList(params, "owner", [currentUserId]),
    statuses: readList(params, "status", ["Active"]),
  };
}

type ToolbarProps = { filters: PipelineFilters; users: User[]; currentUserId: UserId; count: number; total: number; onNewDeal: () => void };

export function PipelineToolbar({ filters, users, currentUserId, count, total, onNewDeal }: ToolbarProps) {
  const [, setParams] = useSearchParams();
  const setView = (view: string) =>
    setParams(
      (next) => {
        next.set("view", view);
        return next;
      },
      { preventScrollReset: true },
    );

  const views = (
    <Segmented role="group" aria-label="View">
      {(["board", "list"] as const).map((view) => (
        <button key={view} type="button" className="segmented__option" aria-pressed={filters.view === view} onClick={() => setView(view)}>
          {view === "board" ? "Board" : "List"}
        </button>
      ))}
    </Segmented>
  );

  return (
    <FilterBar
      shown={count}
      total={total}
      before={
        <>
          {views}
          <TextSearch label="Search deals" placeholder="Project or company" />
        </>
      }
      filters={[
        // Attio Deal_V2 "Deal Type" (Sell-side, Buy-side); no default, so both show.
        { kind: "list", key: "side", label: "Side", options: [{ value: "sell", label: "Sell-side" }, { value: "buy", label: "Buy-side" }] },
        { kind: "list", key: "owner", label: "Owner", options: users.filter((user) => user.role === "Advisor").map((user) => ({ value: user.id, label: user.name })), fallback: [currentUserId] },
        { kind: "list", key: "status", label: "Status", options: [...DEAL_STATUSES], fallback: ["Active"] },
      ]}
    >
      <button type="button" className="button" onClick={onNewDeal}>
        New deal
      </button>
    </FilterBar>
  );
}
