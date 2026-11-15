import type { ReactNode } from "react";
import { ENRICH_COST_CREDITS } from "../../demo/api";
import type { Deal } from "../../demo/types";
import { ActionsMenu } from "./actions-menu";

type Props = {
  picked: { inAttio: boolean; enriched: boolean }[];
  /** Deals a ticked company can join: sell-side mandates for buyers, buy-side for sellers. */
  deals: Deal[];
  creditsLeft: number;
  roleNoun: "buyer role" | "seller role";
  leadSide: "buy" | "sell";
  onEnrich: () => void;
  onAddRoles: () => void;
  onAddToDeal: (dealId: string) => void;
  onNewLead: () => void;
  /** Extra actions for the ticked rows, such as Ask if open to selling. */
  children?: ReactNode;
};

// PRD S2: every action works on the ticked rows and is one click once rows are ticked.
// Companies already in Attio are never added again; they can still be enriched and join a deal.
export function SearchActions({ picked, deals, creditsLeft, roleNoun, leadSide, onEnrich, onAddRoles, onAddToDeal, onNewLead, children }: Props) {
  const toEnrich = picked.filter((row) => !row.enriched).length;
  const cost = toEnrich * ENRICH_COST_CREDITS;
  const newNames = picked.filter((row) => !row.inAttio).length;

  return (
    <div className="search-actions">
      <span className="search-actions__count">{picked.length} selected</span>
      <button type="button" className="button button--small button--quiet" disabled={toEnrich === 0 || cost > creditsLeft} onClick={onEnrich}>
        Enrich for {cost} credits
      </button>
      <span className="muted">{creditsLeft} Apollo credits left</span>
      <button type="button" className="button button--small" disabled={newNames === 0} onClick={onAddRoles}>
        {newNames === 1 ? `Add as ${roleNoun}` : `Add ${newNames ? `${newNames} ` : ""}as ${roleNoun}s`}
      </button>
      {children}
      <ActionsMenu
        label="Add to deal"
        itemName="the selected companies"
        disabled={picked.length === 0 || deals.length === 0}
        actions={deals.map((deal) => ({ panel: deal.id, label: deal.codeName }))}
        onPick={onAddToDeal}
      />
      <button type="button" className="button button--small button--quiet" disabled={picked.length !== 1} onClick={onNewLead}>
        New {leadSide}-side lead
      </button>
    </div>
  );
}
