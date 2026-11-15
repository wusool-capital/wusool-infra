// Engagement letter terms and defaults, taken from the Wusool skills that draft the
// documents (sell-side proposal and agreement, simplified agreement, buy-side proposal)
// and from the client NDA template. Fees are computed here in code, never by AI
// (CLAUDE.md AI usage policy).
import type { Deal } from "../demo/types";
import { formatUsd } from "./format";

export type AgreementType = "sell-structured" | "sell-listing" | "buy";

export const AGREEMENT_LABELS: Record<AgreementType, string> = {
  "sell-structured": "Structured sale process",
  "sell-listing": "Platform listing",
  buy: "Buy-side search",
};

// The client NDA is the one-way confidentiality agreement a seller signs before sharing
// information with Wusool. wusool-nda is a different document: the NDA buyers sign.
const CLIENT_NDA = { name: "Confidentiality agreement", skill: "Client NDA template", short: "the confidentiality agreement" };

/** Documents each agreement type produces, with the skill or template that drafts each one. */
export const AGREEMENT_DOCUMENTS: Record<AgreementType, { name: string; skill: string; short: string }[]> = {
  "sell-structured": [
    { name: "Proposal", skill: "wusool-sellside-proposal", short: "our proposal" },
    { name: "Sell-side agreement", skill: "wusool-sellside-agreement", short: "the engagement agreement" },
    CLIENT_NDA,
  ],
  "sell-listing": [
    { name: "Simplified sell-side agreement", skill: "wusool-sellside-simplified-agreement", short: "the engagement agreement" },
    CLIENT_NDA,
  ],
  // The client NDA template covers a company being sold, so the buy-side pack has none.
  buy: [
    { name: "Buy-side proposal", skill: "wusool-buyside-proposal", short: "our proposal" },
    { name: "Buy-side agreement", skill: "wusool-finder-fee-agreement", short: "the engagement agreement" },
  ],
};

export function needsClientNda(agreement: AgreementType) {
  return AGREEMENT_DOCUMENTS[agreement].includes(CLIENT_NDA);
}

export const NDA_LAWS = ["ADGM courts", "DIFC courts", "Onshore Dubai Courts"] as const;

/** Values the client NDA template leaves blank. Clause 3.4 needs the client's own sectors. */
export type ClientNdaDetails = {
  legalName: string;
  jurisdiction: string;
  registration: string;
  address: string;
  competitorSectors: string;
  law: (typeof NDA_LAWS)[number];
  clientSignatory: string;
};

export function defaultNdaDetails(deal: Deal, clientSignatory: string): ClientNdaDetails {
  return {
    legalName: deal.clientLegal?.name ?? "",
    jurisdiction: deal.clientLegal?.jurisdiction ?? "",
    registration: deal.clientLegal?.registration ?? "",
    address: deal.clientLegal?.address ?? "",
    competitorSectors: deal.sector,
    law: NDA_LAWS[0],
    clientSignatory,
  };
}

export const STAKES = ["Full sale", "Majority", "Minority", "Phased"] as const;
export const FEE_TRIGGERS = [
  "Wusool buyers and any buyer who used Wusool listings, materials or data room",
  "Wusool-introduced buyers only",
] as const;
export const LISTING_CHANNELS = [
  "Anonymised on listing platforms and the Wusool network",
  "Named platforms only",
  "Wusool network only, no public listing",
] as const;
export const GOVERNING_LAWS = ["Onshore Dubai Courts", "DIFC"] as const;
export const VAT_OPTIONS = ["Inclusive in fee", "Exclusive"] as const;
export const SIGNATORIES = ["Jules, Co-Founder and COO", "Hugo, Co-Founder and CEO"] as const;

export type EngagementTerms = {
  agreement: AgreementType;
  // Structured sale (sell-side proposal skill)
  clientBuyerFeePct: number;
  ourBuyerFeePct: number;
  retainerUsd: number;
  retainerMonths: number;
  stake: (typeof STAKES)[number];
  // Platform listing (simplified agreement skill)
  listingFeePct: number;
  listingMinUsd: number;
  feeTrigger: (typeof FEE_TRIGGERS)[number];
  channels: (typeof LISTING_CHANNELS)[number];
  law: (typeof GOVERNING_LAWS)[number];
  vat: (typeof VAT_OPTIONS)[number];
  termMonths: number;
  // Buy-side (buy-side proposal skill): Tier 1 introductions, Tier 2 full support
  tier1FeePct: number;
  tier2FeePct: number;
  tier2MinUsd: number;
  // Shared
  kickoff: string;
  targetClose: string;
  signatory: (typeof SIGNATORIES)[number];
};

// Small owner-run businesses go to a platform listing with no retainer
// (simplified agreement skill); larger ones to a structured process.
const LISTING_BELOW_USD = 3_000_000;

export function defaultTerms(deal: Deal, today: string): EngagementTerms {
  const agreement: AgreementType =
    deal.side === "buy" ? "buy" : (deal.valueUsd ?? 0) < LISTING_BELOW_USD ? "sell-listing" : "sell-structured";
  return {
    agreement,
    clientBuyerFeePct: 3,
    ourBuyerFeePct: 5,
    retainerUsd: 5_000,
    retainerMonths: 4,
    stake: "Full sale",
    listingFeePct: 8,
    listingMinUsd: 10_000,
    feeTrigger: FEE_TRIGGERS[0],
    channels: LISTING_CHANNELS[0],
    law: GOVERNING_LAWS[0],
    vat: VAT_OPTIONS[0],
    termMonths: 12,
    tier1FeePct: 3,
    tier2FeePct: 5,
    tier2MinUsd: 40_000,
    kickoff: addDays(today, 7),
    targetClose: addMonths(today, 6),
    signatory: SIGNATORIES[0],
  };
}

function addDays(day: string, days: number) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function addMonths(day: string, months: number) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() + months);
  return date.toISOString().slice(0, 7);
}

/** Worked fee examples at the deal value, as each skill requires, plus any warning. */
export function feeExamples(terms: EngagementTerms, valueUsd: number | undefined) {
  if (!valueUsd) return { lines: [], warning: "Set the deal value to see the fee at the likely price." };
  if (Object.values(terms).some((value) => typeof value === "number" && Number.isNaN(value))) {
    return { lines: [], warning: "Fill every amount to see the fee." };
  }
  const pct = (rate: number) => (valueUsd * rate) / 100;
  const retainerTotal = terms.retainerUsd * terms.retainerMonths;

  if (terms.agreement === "sell-structured") {
    // The retainer is credited against the success fee, so the total is the larger of the two.
    const client = Math.max(pct(terms.clientBuyerFeePct), retainerTotal);
    const ours = Math.max(pct(terms.ourBuyerFeePct), retainerTotal);
    return {
      lines: [`Buyers the client brings: ${formatUsd(client)} in total, retainer included`, `Buyers we bring: ${formatUsd(ours)} in total, retainer included`],
      warning: retainerTotal > pct(terms.clientBuyerFeePct) ? "The retainer would exceed the success fee on client-sourced buyers." : "",
    };
  }
  if (terms.agreement === "sell-listing") {
    return { lines: [`Success fee: ${formatUsd(Math.max(pct(terms.listingFeePct), terms.listingMinUsd))}`], warning: "" };
  }
  const tier1 = pct(terms.tier1FeePct);
  const tier2 = Math.max(pct(terms.tier2FeePct), terms.tier2MinUsd, retainerTotal);
  return {
    lines: [`Tier 1, introductions: ${formatUsd(tier1)} at closing`, `Tier 2, full support: ${formatUsd(tier2)} in total, retainer included`],
    warning: tier1 < tier2 / 2 ? "Tier 1 costs less than half of Tier 2 at this size." : "",
  };
}
