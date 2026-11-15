// Invented demo data for the Mandates tab (Deal view). Falcon, Pearl, Cedar and Atlas are
// filled in; other mandates show the empty states.
import { MATERIAL_NAMES } from "./types";
import type {
  Counterparty,
  Material,
  MaterialItem,
  MaterialName,
  MaterialStatus,
  HistoryEvent,
  MandateDetails,
  Offer,
  Person,
  Suggestion,
} from "./types";

export const mandatePeople: Person[] = [
  { id: "p-ziad", name: "Ziad Mansour", org: "Petra Animal Health", role: "buyer", title: "CEO" },
  { id: "p-lina", name: "Lina Farah", org: "Crescent Vet Partners", role: "buyer", title: "Head of Corporate Development" },
  { id: "p-noura", name: "Noura Al Amri", org: "Smileline Group", role: "buyer", title: "CFO" },
  { id: "p-james", name: "James Okafor", org: "Roastworks Holdings", role: "buyer", title: "Group COO" },
  { id: "p-fahad", name: "Fahad Al Qahtani", org: "Lumen Dental Clinics", role: "other", title: "Founder" },
  { id: "p-saad", name: "Saad Al Mutairi", org: "Kiteway Logistics", role: "other", title: "Owner" },
];

export const mandateDetails: MandateDetails[] = [
  {
    dealId: "d-falcon",
    financials: { fy: "FY2025", revenueUsd: 6_400_000, grossProfitUsd: 3_900_000, ebitdaUsd: 1_600_000, askingPriceUsd: 14_500_000 },
    nextStepDue: "2026-11-12",
    stageEnteredAt: { Lead: "2026-07-20", Qualified: "2026-08-04", Engaged: "2026-08-20", "Mandate signed": "2026-09-04", Preparation: "2026-09-10", Outreach: "2026-10-20" },
  },
  {
    dealId: "d-pearl",
    financials: { fy: "FY2025", revenueUsd: 5_200_000, grossProfitUsd: 3_400_000, ebitdaUsd: 1_200_000, askingPriceUsd: 9_800_000 },
    nextStepDue: "2026-11-13",
    stageEnteredAt: { Lead: "2026-06-02", Qualified: "2026-06-20", Engaged: "2026-07-10", "Mandate signed": "2026-07-20", Preparation: "2026-07-24", Outreach: "2026-09-01", "Non-binding offers": "2026-10-08" },
  },
  {
    dealId: "d-cedar",
    financials: { fy: "FY2025", revenueUsd: 3_100_000, grossProfitUsd: 1_400_000, ebitdaUsd: 620_000, askingPriceUsd: 6_200_000 },
    nextStepDue: "2026-11-13",
    stageEnteredAt: { Lead: "2026-08-10", Qualified: "2026-08-25", Engaged: "2026-09-08", "Mandate signed": "2026-09-15", Preparation: "2026-09-22" },
  },
  {
    dealId: "d-atlas",
    financials: { fy: "FY2025" },
    nextStepDue: "2026-11-14",
    stageEnteredAt: { Lead: "2026-09-01", Qualified: "2026-09-15", Engaged: "2026-10-01", "Mandate signed": "2026-10-20", Preparation: "2026-10-22", Outreach: "2026-10-25", "Non-binding offers": "2026-10-30" },
  },
];

export const counterparties: Counterparty[] = [
  { id: "c-gulfstone", dealId: "d-falcon", name: "Gulfstone Partners", category: "Financial", hq: "Dubai", status: "Contacted", contactIds: ["p-sara"], lastContactAt: "2026-11-05T10:20:00+04:00", nextStep: "Follow up on the teaser", rationale: "Mid-market fund with two healthcare platforms in the UAE; looking for a vet platform.", website: "gulfstone.example", dataRoom: { lastViewAt: "2026-11-11T07:10:00+04:00", filesOpened: 1 }, outreach: { firstSentAt: "2026-11-05", followUpsSent: 0, lastMessage: "Teaser for Project Falcon sent with a tracked link." } },
  { id: "c-arcadia", dealId: "d-falcon", name: "Arcadia Pet Ventures", category: "Strategic", hq: "Abu Dhabi", status: "Initial conversations", ndaSignedDate: "2026-11-04", contactIds: ["p-layla"], lastContactAt: "2026-11-11T07:52:00+04:00", nextStep: "Send add-back support", rationale: "Owns pet stores and grooming in the UAE; clinics complete its offer.", website: "arcadiapet.example", dataRoom: { lastViewAt: "2026-11-10T21:40:00+04:00", filesOpened: 6 }, outreach: { firstSentAt: "2026-10-28", followUpsSent: 0, repliedAt: "2026-10-29", lastMessage: "Layla asked for add-back support before Monday's committee." } },
  { id: "c-oasis", dealId: "d-falcon", name: "Oasis Growth Fund", category: "Financial", hq: "Riyadh", status: "Contacted", contactIds: ["p-daniel"], lastContactAt: "2026-11-09T11:30:00+04:00", nextStep: "Send the NDA", rationale: "Saudi growth fund entering UAE healthcare services.", website: "oasisgrowth.example", outreach: { firstSentAt: "2026-11-09", followUpsSent: 0, lastMessage: "Teaser for Project Falcon sent; NDA offered." } },
  { id: "c-petra", dealId: "d-falcon", name: "Petra Animal Health", category: "Strategic", hq: "Amman", status: "Initial conversations", ndaSignedDate: "2026-11-03", contactIds: ["p-ziad"], lastContactAt: "2026-11-07T14:00:00+04:00", nextStep: "Send the CIM", rationale: "Regional vet distributor building a clinic network in the GCC.", website: "petraanimal.example", dataRoom: { lastViewAt: "2026-11-06T09:15:00+04:00", filesOpened: 2 }, outreach: { firstSentAt: "2026-10-27", followUpsSent: 1, repliedAt: "2026-11-02", lastMessage: "Ziad signed the NDA and asked for the CIM." } },
  { id: "c-crescent", dealId: "d-falcon", name: "Crescent Vet Partners", category: "Strategic", hq: "Jeddah", status: "Initial conversations", ndaSignedDate: "2026-11-06", contactIds: ["p-lina"], lastContactAt: "2026-11-10T16:40:00+04:00", nextStep: "Send the CIM", rationale: "Runs 11 clinics in KSA; wants a first UAE base.", website: "crescentvet.example", outreach: { firstSentAt: "2026-10-29", followUpsSent: 0, repliedAt: "2026-10-30", lastMessage: "Lina confirmed interest; NDA signed 6 Nov." } },
  { id: "c-harrow", dealId: "d-falcon", name: "Harrow Equity", category: "Financial", hq: "London", status: "Not contacted", contactIds: [], nextStep: "Enrich and send the teaser", rationale: "UK buy-and-build fund with a European vet platform.", website: "harrowequity.example" },
  { id: "c-bluewave", dealId: "d-falcon", name: "Bluewave Pet Care", category: "Strategic", hq: "Doha", status: "Passed", contactIds: [], lastContactAt: "2026-10-30T12:00:00+04:00", nextStep: "None", rationale: "Pet retail group in Qatar.", website: "bluewavepet.example" },

  { id: "c-meridian", dealId: "d-pearl", name: "Meridian Health Holdings", category: "Strategic", hq: "Riyadh", status: "LOI", ndaSignedDate: "2026-09-25", contactIds: ["p-youssef"], lastContactAt: "2026-11-10T14:05:00+04:00", nextStep: "Open the data room", rationale: "Healthcare group adding dental to its clinic network.", website: "meridianhealth.example", dataRoom: { lastViewAt: "2026-11-10T14:05:00+04:00", filesOpened: 12 }, outreach: { firstSentAt: "2026-09-18", followUpsSent: 0, repliedAt: "2026-09-19", lastMessage: "Youssef sent the signed LOI." } },
  { id: "c-smileline", dealId: "d-pearl", name: "Smileline Group", category: "Strategic", hq: "Dubai", status: "Bidding offer", ndaSignedDate: "2026-09-28", contactIds: ["p-noura"], lastContactAt: "2026-11-02T10:00:00+04:00", nextStep: "Tell them the LOI went to another bidder", rationale: "UAE dental chain expanding into KSA.", website: "smileline.example", dataRoom: { lastViewAt: "2026-10-27T18:00:00+04:00", filesOpened: 9 }, outreach: { firstSentAt: "2026-09-20", followUpsSent: 0, repliedAt: "2026-09-22", lastMessage: "Noura submitted an IOI at $9.1M." } },
  { id: "c-orchid", dealId: "d-pearl", name: "Orchid Dental Partners", category: "Financial", hq: "Bahrain", status: "Passed", contactIds: [], lastContactAt: "2026-10-12T09:00:00+04:00", nextStep: "None", rationale: "Dental-focused fund.", website: "orchiddental.example" },

  { id: "c-roastworks", dealId: "d-cedar", name: "Roastworks Holdings", category: "Strategic", hq: "Dubai", status: "Not contacted", contactIds: ["p-james"], nextStep: "Send the teaser once approved", rationale: "Coffee group with 30 cafes; wants its own roastery.", website: "roastworks.example" },
  { id: "c-gulfcafe", dealId: "d-cedar", name: "Gulf Cafe Group", category: "Strategic", hq: "Kuwait City", status: "Not contacted", contactIds: [], nextStep: "Enrich and send the teaser", rationale: "Franchise operator moving into supply.", website: "gulfcafe.example" },

  { id: "c-sandcrest", dealId: "d-atlas", name: "Sandcrest Freight", category: "Strategic", hq: "Dammam", status: "LOI", ndaSignedDate: "2026-11-10", contactIds: ["p-faisal"], lastContactAt: "2026-11-10T18:10:00+04:00", nextStep: "Agree LOI terms", rationale: "Freight forwarder with $11M revenue and a bonded warehouse.", website: "sandcrest.example", dataRoom: { lastViewAt: "2026-11-10T19:00:00+04:00", filesOpened: 3 }, outreach: { firstSentAt: "2026-10-30", followUpsSent: 0, repliedAt: "2026-11-02", lastMessage: "Faisal agreed to discuss LOI terms." } },
  // Seller list entries: owners approached before any mandate (PRD R1, S3).
  { id: "l-lumen", dealId: "", listName: "Sellers: dental owners, KSA", name: "Lumen Dental Clinics", category: "Strategic", hq: "Jeddah", status: "Contacted", contactIds: ["p-fahad"], lastContactAt: "2026-11-04T10:00:00+04:00", nextStep: "Follow up on the owner approach", rationale: "Five clinics, founder in his sixties with no successor.", website: "lumendental.example", outreach: { firstSentAt: "2026-11-04", followUpsSent: 0, lastMessage: "Asked Fahad if he would discuss a sale in confidence." } },
  { id: "l-brightsmile", dealId: "", listName: "Sellers: dental owners, KSA", name: "Brightsmile Ortho", category: "Strategic", hq: "Riyadh", status: "Not contacted", contactIds: [], nextStep: "Find the owner's contact", rationale: "Orthodontics group with three branches.", website: "brightsmile.example" },
  { id: "l-kiteway", dealId: "", listName: "Sellers: logistics owners, KSA", name: "Kiteway Logistics", category: "Strategic", hq: "Dammam", status: "Initial conversations", contactIds: ["p-saad"], lastContactAt: "2026-11-09T12:00:00+04:00", nextStep: "Book a call with the owner", rationale: "Cold-chain trucking, 60 vehicles.", website: "kiteway.example", outreach: { firstSentAt: "2026-11-03", followUpsSent: 0, repliedAt: "2026-11-09", lastMessage: "Saad replied: open to a call next week." } },
  { id: "c-northstar", dealId: "d-atlas", name: "Northstar Logistics", category: "Strategic", hq: "Riyadh", status: "Initial conversations", contactIds: ["p-rami"], lastContactAt: "2026-11-04T12:00:00+04:00", nextStep: "Ask for 2025 accounts", rationale: "Last-mile operator in Riyadh, owner open to a sale.", website: "northstarlog.example", outreach: { firstSentAt: "2026-10-28", followUpsSent: 1, lastMessage: "Asked Rami for the 2025 accounts." } },
];

export const suggestions: Suggestion[] = [
  { id: "s-medvet", dealId: "d-falcon", name: "Medvet Gulf Holdings", category: "Strategic", hq: "Abu Dhabi", rationale: "Owns animal hospitals in Abu Dhabi; Dubai would double its footprint.", website: "medvetgulf.example" },
  { id: "s-pawprint", dealId: "d-falcon", name: "Pawprint Capital", category: "Financial", hq: "Dubai", rationale: "Family office that invested in two pet care brands in 2025.", website: "pawprint.example" },
  { id: "s-northpaw", dealId: "d-falcon", name: "Northpaw Partners", category: "Financial", hq: "Riyadh", rationale: "Healthcare fund with a mandate for clinic roll-ups.", website: "northpaw.example" },
  { id: "s-vetline", dealId: "d-falcon", name: "Vetline Group", category: "Strategic", hq: "Muscat", rationale: "Vet clinic chain in Oman looking to enter the UAE.", website: "vetline.example" },
];

// What each document needs before it can be drafted (PRD MM1 to MM5, Rosenbaum Exhibit 6.5,
// Marks ch. 7, 12 and 16, and the M&A process checklist). The "why" line goes into the client email.
type ItemTemplate = Omit<MaterialItem, "have">;
const client = (name: string, why: string): ItemTemplate => ({ name, why, from: "client" });
const us = (name: string, why: string): ItemTemplate => ({ name, why, from: "us" });

const CHECKLISTS: Record<MaterialName, ItemTemplate[]> = {
  Proposal: [
    client("Legal name of the company", "Names the party the proposal is addressed to."),
    client("Full or majority sale", "Sets the scope of the mandate."),
    client("Revenue and EBITDA, last year", "Sizes the deal for the fee examples."),
    us("Fee tier", "The proposal skill fills the fee table from it."),
    us("Kickoff date", "Starts the timeline in the proposal."),
  ],
  "Client NDA": [
    client("Legal name and licence number", "Identifies the party bound by confidentiality."),
    client("Registered address", "Required in the notices clause."),
    client("Signatory name and title", "Confirms who signs for the company."),
    us("Governing law", "Onshore, DIFC or ADGM courts."),
  ],
  "Engagement contract": [
    us("Signed proposal", "The contract follows the agreed proposal."),
    client("Trade licence", "Proves the business can operate and who holds it."),
    client("Memorandum of association", "Shows who owns the shares and who may sign."),
    us("Fee terms agreed", "Copied from the proposal into the contract."),
    us("Term and exclusivity", "How long we act and on what terms."),
  ],
  Financials: [
    client("2023 accounts", "Buyers value the business on its last three years."),
    client("2024 accounts", "Buyers value the business on its last three years."),
    client("2025 accounts", "The latest year sets the price."),
    client("Management accounts, year to date", "Shows the business is on track this year."),
    client("12 months of bank statements", "Tests that reported revenue reached the bank."),
    client("2025 VAT returns", "A second check on revenue."),
    client("Owner pay and one-time costs with evidence", "Supports the adjustments to EBITDA."),
    us("Normalised EBITDA reconciled to net income", "The figure buyers price on."),
  ],
  Teaser: [
    us("Anonymous business description", "Lets buyers judge fit without knowing the name."),
    us("Sector and city", "The first filter every buyer applies."),
    us("3 to 5 investment highlights", "Why a buyer should ask for the CIM."),
    us("Revenue and EBITDA, last 2 to 3 years", "Taken from the approved financials."),
    client("Reason for sale and transaction sought", "Buyers ask this first."),
    us("Code name", "Keeps the client confidential."),
  ],
  CIM: [
    us("Executive summary and investment highlights", "Opens the CIM."),
    client("History, products and services", "Only the owner knows the full story."),
    client("Top 10 customers with revenue share", "Buyers check how much revenue depends on a few clients."),
    client("Org chart and who stays after the sale", "Buyers price in management continuity."),
    us("Market and competition", "Places the business in its market."),
    us("Growth opportunities and risks", "Frames the upside a buyer pays for."),
    us("Approved financials", "From the Financials card."),
    client("1 to 2 year forecast", "Built with the owner; a simple one is enough."),
  ],
  "Data room": [
    client("Trade licence and MOA", "Legal basics every buyer checks first."),
    client("Shareholder register", "Confirms who must sign the sale."),
    client("Key customer and supplier contracts", "Buyers test change-of-control clauses."),
    client("Leases", "Rent and term affect the price."),
    client("Employee agreements", "Shows end-of-service liabilities."),
    client("Debt schedule", "Debt is repaid from the price at closing."),
    client("VAT and corporate tax registration", "Tax compliance is a deal-killer check."),
    client("Sector licences", "Clinics and labs need their own licences to transfer."),
    us("Teaser and CIM uploaded", "Buyers read these first in VantageKit."),
  ],
};

// Financials has no skill yet, so its Claude prompt carries the checklist without one.
const SKILLS: Partial<Record<MaterialName, string>> = {
  Proposal: "wusool-sellside-proposal",
  "Client NDA": "wusool-nda",
  "Engagement contract": "wusool-sellside-agreement",
  Teaser: "sell-side-one-pager",
  CIM: "wusool-cim",
};

const SELL_FEES = ["Success fee: 3% on buyers the client brings, 5% on buyers we bring", "Retainer: $5,000 per month for up to 4 months, credited against the success fee"];

type Seed = { skill?: string; status: MaterialStatus; date?: string; version?: string; missing?: string[]; mainTerms?: string[]; feeTerms?: string[] };

function material(dealId: string, name: MaterialName, seed: Seed): Material {
  const missing = seed.missing ?? [];
  return {
    id: `mat-${dealId}-${name.toLowerCase().replaceAll(" ", "-")}`,
    dealId,
    name,
    skill: seed.skill ?? SKILLS[name],
    status: seed.status,
    date: seed.date,
    version: seed.version,
    items: CHECKLISTS[name].map((item) => ({ ...item, have: !missing.includes(item.name) })),
    mainTerms: seed.mainTerms ?? [],
    feeTerms: seed.feeTerms ?? [],
  };
}

/** Every deal from Engaged on gets the full set, Not started, until someone works on it. Buy-side: the client paper trail only. */
export function startingMaterials(dealId: string, side: "sell" | "buy"): Material[] {
  const names = side === "sell" ? MATERIAL_NAMES : MATERIAL_NAMES.slice(0, 3);
  return names.map((name) => material(dealId, name, { skill: name === "Proposal" && side === "buy" ? "wusool-buyside-proposal" : undefined, status: "Not started", missing: ALL(name) }));
}

const ALL = (name: MaterialName) => CHECKLISTS[name].map((item) => item.name);

export const materials: Material[] = [
  material("d-falcon", "Proposal", { status: "Signed", date: "2026-09-02", mainTerms: ["Sell-side, full sale", "Kickoff 8 Sep 2026"], feeTerms: SELL_FEES }),
  material("d-falcon", "Client NDA", { status: "Signed", date: "2026-08-28", mainTerms: ["Confidentiality agreement, one-way", "Governing law: ADGM courts"] }),
  material("d-falcon", "Engagement contract", { status: "Signed", date: "2026-09-04", mainTerms: ["Signed by Omar Khalil", "Term: until closing", "Governing law: Onshore Dubai Courts"], feeTerms: SELL_FEES }),
  material("d-falcon", "Financials", { status: "Approved", version: "v2" }),
  material("d-falcon", "Teaser", { status: "Approved", version: "v3" }),
  material("d-falcon", "CIM", { status: "Approved", version: "v3" }),
  material("d-falcon", "Data room", { status: "Live", date: "2026-10-30", missing: ["Leases", "Employee agreements"] }),

  material("d-pearl", "Proposal", { status: "Signed", date: "2026-07-14", mainTerms: ["Sell-side, majority sale"], feeTerms: SELL_FEES }),
  material("d-pearl", "Client NDA", { status: "Signed", date: "2026-07-10", mainTerms: ["Confidentiality agreement, one-way"] }),
  material("d-pearl", "Engagement contract", { status: "Signed", date: "2026-07-20", mainTerms: ["Signed by Karim Aziz", "Governing law: DIFC courts"], feeTerms: SELL_FEES }),
  material("d-pearl", "Financials", { status: "Drafted", version: "v1", missing: ["2025 VAT returns", "Owner pay and one-time costs with evidence"] }),
  material("d-pearl", "Teaser", { status: "Approved", version: "v2" }),
  material("d-pearl", "CIM", { status: "Approved", version: "v2" }),
  material("d-pearl", "Data room", { status: "Live", date: "2026-10-05", missing: ["Leases", "Sector licences", "Debt schedule"] }),

  material("d-cedar", "Proposal", { status: "Signed", date: "2026-10-15", mainTerms: ["Sell-side, full sale"], feeTerms: SELL_FEES }),
  material("d-cedar", "Client NDA", { status: "Signed", date: "2026-10-12", mainTerms: ["Confidentiality agreement, one-way"] }),
  material("d-cedar", "Engagement contract", { status: "Sent", date: "2026-11-03", mainTerms: ["Sent to Hamad Saeed on 3 Nov 2026"], feeTerms: SELL_FEES, missing: ["Memorandum of association"] }),
  material("d-cedar", "Financials", { status: "Not started", missing: ["2023 accounts", "2025 accounts", "Management accounts, year to date", "12 months of bank statements", "2025 VAT returns", "Owner pay and one-time costs with evidence", "Normalised EBITDA reconciled to net income"] }),
  material("d-cedar", "Teaser", { status: "Drafted", version: "v1", missing: ["Revenue and EBITDA, last 2 to 3 years"] }),
  material("d-cedar", "CIM", { status: "Not started", missing: ["Org chart and who stays after the sale", "Market and competition", "Growth opportunities and risks", "Approved financials", "1 to 2 year forecast"] }),
  material("d-cedar", "Data room", { status: "Not started", missing: ALL("Data room").filter((name) => name !== "Trade licence and MOA") }),

  // Buy-side: the paper trail with the client only; targets' NDAs live in the Targets tab.
  material("d-atlas", "Proposal", { skill: "wusool-buyside-proposal", status: "Signed", date: "2026-10-20", mainTerms: ["Buy-side, Tier 2 full support"], feeTerms: ["Tier 2: 5% success fee, $40,000 minimum", "Retainer: $5,000 per month for up to 4 months, credited"] }),
  material("d-atlas", "Client NDA", { status: "Not started", missing: ["Registered address", "Signatory name and title"] }),
  material("d-atlas", "Engagement contract", { status: "Signed", date: "2026-10-27", mainTerms: ["Signed by Priya Menon"], feeTerms: ["Tier 2: 5% success fee, $40,000 minimum"] }),
];

export const offers: Offer[] = [
  { id: "o-arcadia", dealId: "d-falcon", counterpartyId: "c-arcadia", type: "IOI", date: "2026-11-10", evUsd: 13_200_000, cashPct: 70, deferredPct: 15, earnoutPct: 15, conditions: "Founder stays 18 months; vet team retention plan", ddWeeks: 8, exclusivityWeeks: 6, status: "Received", documentName: "Arcadia IOI 10 Nov.pdf" },
  { id: "o-crescent", dealId: "d-falcon", counterpartyId: "c-crescent", type: "IOI", date: "2026-11-11", evUsd: 12_500_000, cashPct: 90, deferredPct: 10, earnoutPct: 0, conditions: "Licence transfer approved before closing", ddWeeks: 6, exclusivityWeeks: 4, status: "Received", documentName: "Crescent IOI 11 Nov.pdf" },
  { id: "o-meridian", dealId: "d-pearl", counterpartyId: "c-meridian", type: "LOI", date: "2026-11-08", evUsd: 9_800_000, cashPct: 80, deferredPct: 10, earnoutPct: 10, conditions: "Insurer contracts confirmed; lab lease renewed", ddWeeks: 8, exclusivityWeeks: 6, status: "Accepted", documentName: "Meridian LOI signed.pdf" },
  { id: "o-smileline", dealId: "d-pearl", counterpartyId: "c-smileline", type: "IOI", date: "2026-10-28", evUsd: 9_100_000, cashPct: 100, deferredPct: 0, earnoutPct: 0, conditions: "None", ddWeeks: 10, exclusivityWeeks: 8, status: "Rejected", documentName: "Smileline IOI.pdf" },
  { id: "o-sandcrest", dealId: "d-atlas", counterpartyId: "c-sandcrest", type: "IOI", date: "2026-11-06", evUsd: 24_000_000, cashPct: 75, deferredPct: 15, earnoutPct: 10, conditions: "Bonded warehouse licence stays valid", ddWeeks: 8, exclusivityWeeks: 6, status: "Sent" },
];

export const history: HistoryEvent[] = [
  { id: "h-1", dealId: "d-falcon", at: "2026-11-11T07:52:00+04:00", type: "Email", counterpartyId: "c-arcadia", text: "Layla Haddad asked for support on two 2025 add-backs before Monday's investment committee.", source: "Gmail, Jules's inbox" },
  { id: "h-2", dealId: "d-falcon", at: "2026-11-11T07:10:00+04:00", type: "Document", counterpartyId: "c-gulfstone", text: "Gulfstone Partners opened the teaser (2 views).", source: "VantageKit" },
  { id: "h-3", dealId: "d-falcon", at: "2026-11-11T06:40:00+04:00", type: "Offer", counterpartyId: "c-crescent", text: "IOI received from Crescent Vet Partners: $12.5M, 90% cash at close.", source: "Gmail, attachment Crescent IOI 11 Nov.pdf" },
  { id: "h-4", dealId: "d-falcon", at: "2026-11-10T21:40:00+04:00", type: "Document", counterpartyId: "c-arcadia", text: "Arcadia Pet Ventures downloaded CIM v3.", source: "VantageKit" },
  { id: "h-5", dealId: "d-falcon", at: "2026-11-10T15:00:00+04:00", type: "Meeting", text: "Call with Omar Khalil: agreed the buyer shortlist and the first-round deadline of 12 Nov.", source: "Scribe note in Attio" },
  { id: "h-6", dealId: "d-falcon", at: "2026-11-10T12:20:00+04:00", type: "Offer", counterpartyId: "c-arcadia", text: "IOI received from Arcadia Pet Ventures: $13.2M, 70% cash at close.", source: "Gmail, attachment Arcadia IOI 10 Nov.pdf" },
  { id: "h-7", dealId: "d-falcon", at: "2026-11-06T17:30:00+04:00", type: "Buyer status", counterpartyId: "c-crescent", text: "Crescent Vet Partners signed the NDA.", source: "DocuSign" },
  { id: "h-8", dealId: "d-falcon", at: "2026-10-30T12:00:00+04:00", type: "Decision", counterpartyId: "c-bluewave", text: "Bluewave Pet Care passed.", source: "Email from Bluewave, 30 Oct 2026", decision: { who: "Jules", why: "Retail only; no appetite for clinics." } },
  { id: "h-9", dealId: "d-falcon", at: "2026-10-21T10:00:00+04:00", type: "Stage", text: "Stage moved to Outreach.", source: "Attio" },
  { id: "h-10", dealId: "d-pearl", at: "2026-11-10T14:05:00+04:00", type: "Offer", counterpartyId: "c-meridian", text: "Meridian Health signed the LOI at $9.8M with 6 weeks of exclusivity.", source: "Gmail, attachment Meridian LOI signed.pdf" },
  { id: "h-11", dealId: "d-pearl", at: "2026-11-02T10:00:00+04:00", type: "Decision", counterpartyId: "c-smileline", text: "Smileline IOI rejected.", source: "Meeting with Karim Aziz, 2 Nov 2026", decision: { who: "Karim Aziz with Jules", why: "Lower price and 10 weeks of diligence." } },
  { id: "h-12", dealId: "d-cedar", at: "2026-11-10T16:05:00+04:00", type: "Email", text: "Nadia Farouk sent the draft 2025 management accounts.", source: "Gmail, Jules's inbox" },
  { id: "h-13", dealId: "d-atlas", at: "2026-11-10T18:10:00+04:00", type: "Buyer status", counterpartyId: "c-sandcrest", text: "Sandcrest Freight signed the NDA.", source: "DocuSign" },
];
