import type { ContextReadingRead } from "@/gen/types/ContextReadingRead";
import type { DiscrepancyRead } from "@/gen/types/DiscrepancyRead";
import { money } from "@/lib/format";

// Mirrors the field names advisors see in Slack's /edit-buyer.
export const CRITERION_LABELS: Record<DiscrepancyRead["criterion"], string> = {
  vertical: "Target vertical",
  geography: "Target region or country",
  ticket_band: "Check size",
  ebitda: "EBITDA range",
};

function range(
  low: number | null | undefined,
  high: number | null | undefined,
): string | null {
  if (low != null && high != null) return `${money(low)}–${money(high)}`;
  if (low != null) return `at least ${money(low)}`;
  if (high != null) return `up to ${money(high)}`;
  return null;
}

// How the advisor's note was read, one line per criterion, so a misread is visible.
export function contextLines(context: ContextReadingRead): string[] {
  const lines: string[] = [];
  const { verticals, countries, seller_status: sellerStatus } = context;
  if (verticals.length > 0) lines.push(`Sector: ${verticals.join(" or ")}`);
  const place = [context.region, ...countries].filter(
    (v): v is string => typeof v === "string" && v.length > 0,
  );
  if (place.length > 0) lines.push(`Geography: ${place.join(", ")}`);
  const ticket = range(context.ticket_low, context.ticket_high);
  if (ticket) lines.push(`Ticket: ${ticket}`);
  const ebitda = range(context.ebitda_low, context.ebitda_high);
  if (ebitda) lines.push(`EBITDA: ${ebitda}`);
  if (context.ev_ceiling != null)
    lines.push(`EV: up to ${money(context.ev_ceiling)}`);
  const revenue = range(context.revenue_low, context.revenue_high);
  if (revenue) lines.push(`Revenue: ${revenue}`);
  if (sellerStatus.length > 0)
    lines.push(`Seller status: ${sellerStatus.join(", ")}`);
  return lines;
}
