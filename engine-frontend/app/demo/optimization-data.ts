// Invented numbers for Engine optimization (PRD EO1, EO2). Once live these come from the
// Engine's activity and bottleneck logs and from Attio stage history.
import type { Bottleneck, ConversionRow, ReplyStat, WaitingClient } from "./types";

/** When each active deal entered its current stage. */
export const stageEnteredAt: Record<string, string> = {
  "d-falcon": "2026-10-20", "d-pearl": "2026-10-08", "d-cedar": "2026-09-22", "d-atlas": "2026-10-30", "d-onyx": "2026-10-05",
  "d-quartz": "2026-10-28", "d-dune": "2026-11-03", "d-mirage": "2026-10-15", "d-juniper": "2026-10-12", "d-orbit": "2026-10-24",
  "d-saffron": "2026-10-01", "d-coral": "2026-10-29",
};

/** Median days in each stage over the last 12 months. */
export const stageMedianDays: Record<string, number> = {
  Lead: 14, Qualified: 21, Engaged: 12, "Mandate signed": 10, Preparation: 30, Outreach: 35, "Non-binding offers": 21, "Due diligence": 45, Closing: 30, Closed: 0,
};

export const waitingClients: WaitingClient[] = [
  { id: "w-1", dealId: "d-pearl", personId: "p-karim", subject: "Request list: lease agreements", lastFromClientAt: "2026-11-06T09:10:00+04:00" },
  { id: "w-2", dealId: "d-onyx", personId: "p-rania", subject: "Re: engagement terms", lastFromClientAt: "2026-11-02T15:30:00+04:00" },
];

export const replyStats: ReplyStat[] = [
  { template: "Teaser introduction", sector: "Veterinary", sent: 14, replied: 6 },
  { template: "Teaser introduction", sector: "Dental", sent: 9, replied: 2 },
  { template: "Follow-up", sector: "Veterinary", sent: 11, replied: 3 },
  { template: "Follow-up", sector: "Dental", sent: 7, replied: 1 },
  { template: "Owner approach", sector: "Dental", sent: 12, replied: 4 },
  { template: "Owner approach", sector: "Logistics", sent: 8, replied: 3 },
  { template: "Data room invitation", sector: "Veterinary", sent: 5, replied: 5 },
];

/** Deals that reached each stage in the last 12 months, and how many moved to the next. */
export const conversion: ConversionRow[] = [
  { stage: "Lead", reached: 48, advanced: 22 },
  { stage: "Qualified", reached: 22, advanced: 14 },
  { stage: "Engaged", reached: 14, advanced: 11 },
  { stage: "Mandate signed", reached: 11, advanced: 10 },
  { stage: "Preparation", reached: 10, advanced: 8 },
  { stage: "Outreach", reached: 8, advanced: 5 },
  { stage: "Non-binding offers", reached: 5, advanced: 4 },
  { stage: "Due diligence", reached: 4, advanced: 3 },
  { stage: "Closing", reached: 3, advanced: 3 },
];

export const bottlenecks: Bottleneck[] = [
  { id: "bn-1", at: "2026-11-10T11:20:00+04:00", byId: "hugo", where: "Deal view", dealId: "d-dune", what: "Client sends financials as phone photos; reconciliation stalls for a week.", promoted: false },
  { id: "bn-2", at: "2026-11-06T16:05:00+04:00", byId: "jules", where: "Outreach", what: "Apollo has no owner email for most KSA dental clinics.", promoted: true },
  { id: "bn-3", at: "2026-11-04T09:40:00+04:00", byId: "ramzy", where: "Pipeline", dealId: "d-saffron", what: "Buyer tax questions wait on the client's external accountant.", promoted: false },
];
