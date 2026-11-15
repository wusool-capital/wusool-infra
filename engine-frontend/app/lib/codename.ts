import type { Deal, Person } from "../demo/types";

// PRD guardrail: on a sell-side deal, the client's real name must never reach a buyer.
// Returns the leaked name, or null when the draft is safe to send.
export function findCodenameLeak(text: string, deal: Deal | undefined, recipient: Person | undefined) {
  if (!deal || deal.side !== "sell" || recipient?.role !== "buyer") return null;
  return text.toLowerCase().includes(deal.clientName.toLowerCase()) ? deal.clientName : null;
}
