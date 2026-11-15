import { useState } from "react";
import { Link } from "react-router";
import type { Deal, User } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatMoney } from "../../lib/format";
import { STAGES, type Stage } from "../../lib/stages";
import { useRouteAction } from "../ui/toast";

export function KanbanBoard({ deals, users }: { deals: Deal[]; users: User[] }) {
  const act = useRouteAction("/pipeline");
  const [overStage, setOverStage] = useState<Stage | null>(null);

  // Dragging is a shortcut; the drawer's Stage field does the same for keyboard users.
  const moveTo = (stage: Stage, dealId: string) => {
    setOverStage(null);
    const deal = byId(deals, dealId);
    if (!deal || deal.stage === stage) return;
    act({ intent: "deal-update", id: deal.id, patch: JSON.stringify({ stage }) }, `${deal.codeName} moved to ${stage}.`);
  };

  return (
    <div className="board" aria-label="Deals by stage">
      {STAGES.map((stage) => {
        const column = deals.filter((deal) => deal.stage === stage);
        return (
          <section
            key={stage}
            className="board__column"
            data-over={overStage === stage ? "yes" : "no"}
            aria-labelledby={`stage-${stage}`}
            onDragOver={(event) => {
              event.preventDefault();
              setOverStage(stage);
            }}
            onDragLeave={() => setOverStage(null)}
            onDrop={(event) => moveTo(stage, event.dataTransfer.getData("text/plain"))}
          >
            <h2 className="board__title" id={`stage-${stage}`}>
              {stage} <span className="board__count">{column.length}</span>
            </h2>
            <ul className="board__cards">
              {column.map((deal) => (
                <li key={deal.id}>
                  <Link
                    className="deal-card"
                    to={`?${withDeal(deal.id)}`}
                    preventScrollReset
                    draggable
                    onDragStart={(event) => event.dataTransfer.setData("text/plain", deal.id)}
                  >
                    <span className="deal-card__name">{deal.codeName}</span>
                    <span className="deal-card__meta">
                      {deal.side === "sell" ? "Sell-side" : "Buy-side"}, {deal.sector}
                    </span>
                    <span className="deal-card__next">Next: {deal.nextStep}</span>
                    <span className="deal-card__foot">
                      <span className="deal-card__value">{formatMoney(deal.valueUsd)}</span>
                      <span className="avatar avatar--small" aria-label={`Owner ${byId(users, deal.ownerId)?.name}`}>
                        {byId(users, deal.ownerId)?.name.charAt(0)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            {column.length === 0 && <p className="board__empty">No deals</p>}
          </section>
        );
      })}
    </div>
  );
}

/** Keeps the current filters when opening a deal. */
export function withDeal(dealId: string) {
  const params = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
  params.set("deal", dealId);
  return params.toString();
}
