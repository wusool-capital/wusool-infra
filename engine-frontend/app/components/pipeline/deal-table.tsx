import { useState } from "react";
import { useNavigate } from "react-router";
import type { Deal, DealCounts, User } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatMoney, formatWhen } from "../../lib/format";
import { STAGES } from "../../lib/stages";
import { EmptyState } from "../ui/empty-state";
import { withDeal } from "./kanban-board";

type SortKey = "codeName" | "clientName" | "side" | "stage" | "owner" | "valueUsd" | "lastActivityAt";
type Sort = { key: SortKey; dir: "asc" | "desc" } | null;

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "codeName", label: "Deal" },
  { key: "clientName", label: "Company" },
  { key: "side", label: "Side" },
  { key: "stage", label: "Stage" },
  { key: "owner", label: "Owner" },
  { key: "valueUsd", label: "Value", numeric: true },
  { key: "lastActivityAt", label: "Last activity" },
];

type DealTableProps = { deals: Deal[]; users: User[]; counts: Record<string, DealCounts>; now: string };

export function DealTable({ deals, users, counts, now }: DealTableProps) {
  const navigate = useNavigate();
  const [sort, setSort] = useState<Sort>(null);

  const value = (deal: Deal, key: SortKey): string | number => {
    if (key === "stage") return STAGES.indexOf(deal.stage);
    if (key === "owner") return byId(users, deal.ownerId)?.name ?? "";
    if (key === "valueUsd") return deal.valueUsd ?? -1;
    return deal[key];
  };

  const rows = sort
    ? [...deals].sort((a, b) => {
        const [x, y] = [value(a, sort.key), value(b, sort.key)];
        const order = typeof x === "number" ? x - (y as number) : String(x).localeCompare(String(y));
        // DESIGN.md: first click A to Z, numbers low first, dates newest first.
        const firstDir = sort.key === "lastActivityAt" ? -1 : 1;
        return order * firstDir * (sort.dir === "asc" ? 1 : -1);
      })
    : deals;

  // DESIGN.md: first click sorts, second reverses, third returns to the default order.
  const cycle = (key: SortKey) =>
    setSort(!sort || sort.key !== key ? { key, dir: "asc" } : sort.dir === "asc" ? { key, dir: "desc" } : null);

  const open = (deal: Deal) => navigate(`?${withDeal(deal.id)}`, { preventScrollReset: true });

  if (deals.length === 0) return <EmptyState>No deals match these filters.</EmptyState>;

  return (
    <div className="card card--flush">
      <table className="table table--fixed">
        <colgroup>
          <col style={{ width: "12%" }} />
          <col style={{ width: "11%" }} />
          <col style={{ width: "8%" }} />
          <col style={{ width: "13%" }} />
          <col style={{ width: "6%" }} />
          <col style={{ width: "6%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "6%" }} />
          <col style={{ width: "5%" }} />
          <col style={{ width: "5%" }} />
          <col />
        </colgroup>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={column.numeric ? "num" : undefined}
                aria-sort={sort?.key === column.key ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
              >
                <button type="button" className="th-sort" onClick={() => cycle(column.key)}>
                  {column.label}
                  {sort?.key === column.key && <span aria-hidden="true">{sort.dir === "asc" ? " ↑" : " ↓"}</span>}
                </button>
              </th>
            ))}
            <th scope="col" className="num">In play</th>
            <th scope="col" className="num">NDAs</th>
            <th scope="col" className="num">Offers</th>
            <th scope="col">Next step</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((deal) => (
            <tr
              key={deal.id}
              className="row-clickable"
              tabIndex={0}
              onClick={() => open(deal)}
              onKeyDown={(event) => {
                if (event.key === "Enter") open(deal);
              }}
            >
              <td><span className="cell-title">{deal.codeName}</span></td>
              <td className="cell-clip" title={deal.clientName}>{deal.clientName}</td>
              <td>{deal.side === "sell" ? "Sell-side" : "Buy-side"}</td>
              <td>{deal.stage}</td>
              <td>{byId(users, deal.ownerId)?.name}</td>
              <td className="num">{formatMoney(deal.valueUsd)}</td>
              <td>{formatWhen(deal.lastActivityAt, now)}</td>
              <td className="num">{counts[deal.id]?.buyersInPlay ?? 0}</td>
              <td className="num">{counts[deal.id]?.ndasSigned ?? 0}</td>
              <td className="num">{counts[deal.id]?.offers ?? 0}</td>
              <td className="cell-clip" title={deal.nextStep}>{deal.nextStep}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
