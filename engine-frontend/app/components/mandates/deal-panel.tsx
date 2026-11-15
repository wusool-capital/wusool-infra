import type { DealViewData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { nextAction } from "../../lib/next-action";
import { DecisionDrawer, EmailClientDrawer, FindMoreDrawer, SendCimDrawer } from "./action-drawers";
import { DealDrawer } from "../pipeline/deal-drawer";
import { CounterpartyDrawer } from "./counterparty-drawer";
import { MaterialDrawer } from "./materials-drawers";
import { AddOfferDrawer, OfferDrawer } from "./offer-drawers";
import { usePanel } from "./use-deal";

/** Renders the single open drawer named by ?panel=kind:id (one layer at a time). */
export function DealPanel({ data }: { data: DealViewData }) {
  const { panel, closePanel } = usePanel();
  const [kind, id] = panel.split(":");
  const props = { data, onClose: closePanel };

  switch (kind) {
    case "buyer": {
      const row = byId(data.counterparties, id);
      return row ? <CounterpartyDrawer key={row.id} row={row} {...props} /> : null;
    }
    case "find-more":
      return <FindMoreDrawer {...props} />;
    case "send-cim":
      return <SendCimDrawer {...props} />;
    case "email-client":
      return <EmailClientDrawer {...props} />;
    case "edit":
      return <DealDrawer next={nextAction(data.deal, data, data.now)} deal={data.deal} users={data.users} people={data.people} now={data.now} onClose={closePanel} onDealPage />;
    case "decision":
      return <DecisionDrawer {...props} />;
    case "material": {
      const material = byId(data.materials, id);
      return material ? <MaterialDrawer key={material.id} material={material} {...props} /> : null;
    }
    case "offer": {
      if (id === "new") return <AddOfferDrawer {...props} />;
      const offer = byId(data.offers, id);
      return offer ? <OfferDrawer key={offer.id} offer={offer} {...props} /> : null;
    }
    default:
      return null;
  }
}
