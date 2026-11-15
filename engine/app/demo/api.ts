// The only module routes import for data. Each function stands in for one Toolkit
// endpoint, so going live means replacing a body, not changing a caller.
import { nextAction } from "../lib/next-action";
import { STAGES } from "../lib/stages";
import { DEMO_NOW, seed } from "./data";
import { matchesFilters, type BuyerFilterValues } from "../lib/buyer-filters";
import { anyOf, inRange } from "../lib/filters";
import type { SellerFilterValues } from "../lib/seller-filters";
import * as buyerSeed from "./buyers-data";
import { buyerCandidates, spareCodeNames } from "./buyers-search-data";
import { emailLog } from "./email-log";
import { comparables as comparableSeed } from "./multiples-data";
import { skills as skillSeed } from "./skills-data";
import * as profileSeed from "./profile-data";
import * as optimizationSeed from "./optimization-data";
import { partners as partnerSeed, referredDeals } from "./partners-data";
import { moreScorecards, scorecardHistory } from "./scorecards-data";
import { sellerCandidates } from "./sellers-search-data";
import * as sellerSeed from "./sellers-data";
import * as mandateSeed from "./mandates-data";
import type {
  Deal,
  BuyerPatch,
  BuyerRole,
  BuyersSearchData,
  SellerPatch,
  SellersSearchData,
  ScorecardsData,
  ScorecardMetricInput,
  PartnerPublic,
  PartnerTerms,
  PartnersData,
  OptimizationData,
  MultiplesData,
  SkillsData,
  ProfileData,
  SellersUniverseData,
  BuyersUniverseData,
  CounterpartyStatus,
  DealPatch,
  DealViewData,
  HomeData,
  MaterialStatus,
  NewDealInput,
  OfferInput,
  OfferStatus,
  OutreachData,
  PendingEdit,
  PipelineData,
  Profile,
  UserId,
  WorkstreamStatus,
} from "./types";

// Private copies so demo actions persist until the page reloads.
const db = structuredClone(seed);
const mdb = structuredClone({
  details: mandateSeed.mandateDetails,
  counterparties: mandateSeed.counterparties,
  suggestions: mandateSeed.suggestions,
  materials: mandateSeed.materials,
  offers: mandateSeed.offers,
  history: mandateSeed.history,
  apolloCreditsLeft: 340,
});
db.people.push(...structuredClone(mandateSeed.mandatePeople), ...structuredClone(buyerSeed.buyerPeople), ...structuredClone(sellerSeed.sellerPeople));
const buyers = structuredClone(buyerSeed.buyerRoles);
const candidates = structuredClone(buyerCandidates);
const sellers = structuredClone(sellerSeed.sellerRoles);
const sellerFinds = structuredClone(sellerCandidates);
db.scorecards.push(...structuredClone(moreScorecards));
const partnerRows = structuredClone(partnerSeed);
const bottleneckLog = structuredClone(optimizationSeed.bottlenecks);
const comparableRows = structuredClone(comparableSeed);
const skillRows = structuredClone(skillSeed);
const connectionRows = structuredClone(profileSeed.connections);
let connectorChoices = structuredClone(profileSeed.availableConnectors);
const profileRow = structuredClone(profileSeed.profile);
for (const deal of db.deals) deal.sourcePartnerId = referredDeals[deal.id];

export const CURRENT_USER_ID: UserId = "jules";

function userName(id: UserId) {
  return db.users.find((user) => user.id === id)?.name ?? id;
}

function logActivity(actorId: UserId, text: string) {
  db.activity.unshift({ id: `a-${Date.now()}`, at: DEMO_NOW, actorId, text });
}

export async function getCurrentUser() {
  return structuredClone(db.users.find((user) => user.id === CURRENT_USER_ID)!);
}

export async function getHome(userId: UserId): Promise<HomeData> {
  const mine = <T extends { ownerId: UserId }>(rows: T[]) => rows.filter((row) => row.ownerId === userId);
  const mandates = mine(db.deals).filter((deal) => deal.status === "Active" && deal.stage !== "Closed");
  const scorecard = db.scorecards.find((card) => card.ownerId === userId)!;

  return structuredClone({
    now: DEMO_NOW,
    user: db.users.find((user) => user.id === userId)!,
    users: db.users,
    brief: db.briefs.find((brief) => brief.ownerId === userId)!,
    pendingItems: mine(db.pendingItems),
    emails: mine(db.emails).sort((a, b) => a.receivedAt.localeCompare(b.receivedAt)),
    workstreams: mine(db.workstreams),
    mandates,
    deals: db.deals,
    people: db.people,
    agenda: mine(db.agenda),
    scorecard,
    dataRoom: db.dataRoom
      .filter((event) => mandates.some((deal) => deal.id === event.dealId))
      .sort((a, b) => b.at.localeCompare(a.at)),
    activity: [...db.activity].sort((a, b) => b.at.localeCompare(a.at)),
    toolTabAnswer: db.toolTabAnswers[userId] ?? null,
  });
}

export async function approvePendingItem(userId: UserId, itemId: string, edit: PendingEdit) {
  const item = db.pendingItems.find((row) => row.id === itemId);
  if (!item) return;
  db.pendingItems = db.pendingItems.filter((row) => row.id !== itemId);

  if (item.kind === "stage-change") {
    const deal = db.deals.find((row) => row.id === item.dealId);
    if (!deal) return;
    deal.stage = edit.toStage ?? item.toStage;
    deal.lastActivityAt = DEMO_NOW;
    logActivity(userId, `moved ${deal.codeName} to ${deal.stage}`);
  }
  if (item.kind === "next-step") {
    const deal = db.deals.find((row) => row.id === item.dealId);
    if (deal) deal.nextStep = edit.nextStep ?? item.nextStep;
  }
  if (item.kind === "tasks") {
    (edit.tasks ?? item.tasks).forEach((draft, index) =>
      db.tasks.push({ id: `t-${Date.now()}-${index}`, ownerId: userId, title: draft.title, dueDate: draft.dueDate, dealId: item.dealId, done: false }),
    );
  }
  // Email approvals are the send itself; in the demo nothing leaves the browser.
}

export async function rejectPendingItem(itemId: string) {
  db.pendingItems = db.pendingItems.filter((row) => row.id !== itemId);
}

export async function sendReply(emailId: string) {
  db.emails = db.emails.filter((row) => row.id !== emailId);
}

export async function markNotActionable(emailId: string) {
  db.emails = db.emails.filter((row) => row.id !== emailId);
}

/** Once live this archives the Notion page (it lands in Notion's trash, restorable for 30 days). */
export async function deleteWorkstream(id: string) {
  db.workstreams = db.workstreams.filter((row) => row.id !== id);
}

export async function updateWorkstream(id: string, patch: { status?: WorkstreamStatus; nextStep?: string; dueDate?: string; name?: string }) {
  const workstream = db.workstreams.find((row) => row.id === id);
  if (workstream) Object.assign(workstream, patch);
}

/** PRD K3: tags a person on one metric of `ownerId`'s scorecard; `actorId` is who clicked (Ops tag for advisors). */
export async function tagScorecard(ownerId: UserId, metricId: string, personId: string, actorId: UserId = ownerId) {
  const card = db.scorecards.find((row) => row.ownerId === ownerId);
  const metric = card?.metrics.find((row) => row.id === metricId);
  if (!card || !metric || metric.taggedIds.includes(personId)) return;
  metric.taggedIds.push(personId);
  logActivity(actorId, `tagged a person on ${userName(ownerId)}'s scorecard (${metric.label})`);
}

export async function untagScorecard(ownerId: UserId, metricId: string, personId: string) {
  const metric = db.scorecards.find((row) => row.ownerId === ownerId)?.metrics.find((row) => row.id === metricId);
  if (metric) metric.taggedIds = metric.taggedIds.filter((id) => id !== personId);
}

export async function setScorecardDone(ownerId: UserId, metricId: string, done: boolean) {
  const metric = db.scorecards.find((row) => row.ownerId === ownerId)?.metrics.find((row) => row.id === metricId);
  if (metric) metric.done = done;
}

/** Each person keeps their own list. Kept metrics keep their tags; new ones start empty. */
export async function setScorecardMetrics(ownerId: UserId, inputs: ScorecardMetricInput[]) {
  const card = db.scorecards.find((row) => row.ownerId === ownerId);
  if (!card) return;
  card.metrics = inputs.map((input) => {
    const kept = card.metrics.find((row) => row.id === input.id);
    return { ...input, target: input.kind === "yes-no" ? 1 : input.target, taggedIds: kept?.taggedIds ?? [], done: kept?.done ?? false };
  });
  logActivity(ownerId, `updated ${userName(ownerId)}'s scorecard`);
}

/** Every scorecard plus eight finished weeks (PRD K1, K2). Actuals are the tag counts. */
export async function getScorecards(): Promise<ScorecardsData> {
  return structuredClone({ now: DEMO_NOW, currentUserId: CURRENT_USER_ID, users: db.users, people: db.people, scorecards: db.scorecards, history: scorecardHistory });
}

export async function saveToolTabAnswer(userId: UserId, tools: string[]) {
  db.toolTabAnswers[userId] = { date: DEMO_NOW.slice(0, 10), tools };
}

/** Buyers in play, NDAs signed and offers per deal, for the Pipeline list (was the Mandates tab). */
function dealCounts(): PipelineData["counts"] {
  return Object.fromEntries(
    db.deals.map((deal) => {
      const rows = mdb.counterparties.filter((row) => row.dealId === deal.id);
      return [
        deal.id,
        {
          buyersInPlay: rows.filter((row) => row.status !== "Not contacted" && row.status !== "Passed").length,
          ndasSigned: rows.filter((row) => row.ndaSignedDate).length,
          offers: mdb.offers.filter((offer) => offer.dealId === deal.id).length,
        },
      ];
    }),
  );
}

export async function getPipeline(): Promise<PipelineData> {
  return structuredClone({
    now: DEMO_NOW,
    currentUserId: CURRENT_USER_ID,
    users: db.users,
    people: db.people,
    deals: [...db.deals].sort((a, b) => b.lastActivityAt.localeCompare(a.lastActivityAt)),
    counts: dealCounts(),
    clients: [
      ...sellers.map((row) => ({ id: row.id, side: "sell" as const, name: row.name, sector: row.sector, city: row.hq })),
      ...buyers.map((row) => ({ id: row.id, side: "buy" as const, name: row.name, sector: row.sectors[0] ?? "", city: row.hq })),
    ],
    nextCodeName: freeCodeName(),
    nextActions: Object.fromEntries(
      db.deals.map((deal) => {
        ensureMaterials(deal);
        const forDeal = <T extends { dealId?: string }>(rows: T[]) => rows.filter((row) => row.dealId === deal.id);
        return [deal.id, nextAction(deal, { counterparties: forDeal(mdb.counterparties), materials: forDeal(mdb.materials), offers: forDeal(mdb.offers) }, DEMO_NOW)];
      }),
    ),
  });
}

/**
 * A deal started by hand (an owner calls, a buyer asks for help). The client is an existing role
 * in Attio, or a new company added as a seller or buyer role first, so Attio never gets a duplicate.
 */
export async function createDeal(userId: UserId, input: NewDealInput) {
  let role: { id: string; name: string; contactIds: string[] } | undefined;
  if (input.roleId) {
    role = input.side === "sell" ? sellers.find((row) => row.id === input.roleId) : buyers.find((row) => row.id === input.roleId);
  } else if (input.newName) {
    const id = `${input.side === "sell" ? "sr" : "br"}-${Date.now()}`;
    const base = { id, name: input.newName, hq: input.city, website: "", ownerId: userId, contactIds: [] as string[], notes: "Added from New deal." };
    if (input.side === "sell") {
      sellers.push({ ...base, sector: input.sector, geography: "", estRevenueUsd: 0, openToSelling: "Interested" });
    } else {
      buyers.push({ ...base, type: "Strategic", sectors: [input.sector], geographies: [], checkSizeMinUsd: 0, checkSizeMaxUsd: 0, ebitdaFloorUsd: 0, status: "Active" });
    }
    role = base;
    logActivity(userId, `added ${input.newName} as a ${input.side === "sell" ? "seller" : "buyer"} role`);
  }
  if (!role) return;
  db.deals.push({
    id: `d-${Date.now()}`,
    codeName: input.codeName,
    clientName: role.name,
    side: input.side,
    stage: "Lead",
    status: "Active",
    ownerId: userId,
    sector: input.sector,
    city: input.city,
    contactIds: [...role.contactIds],
    nextStep: input.side === "sell" ? "Book the first call with the owner" : "Book the first call to confirm their target criteria",
    lastActivityAt: DEMO_NOW,
    blurb: "",
  });
  logActivity(userId, `created ${input.codeName}, a ${input.side}-side lead for ${role.name}`);
}

export async function updateDeal(userId: UserId, dealId: string, patch: DealPatch) {
  const deal = db.deals.find((row) => row.id === dealId);
  if (!deal) return;
  if (patch.stage && patch.stage !== deal.stage) {
    logActivity(userId, `moved ${deal.codeName} to ${patch.stage}`);
    const details = mdb.details.find((row) => row.dealId === dealId);
    if (details) details.stageEnteredAt[patch.stage] = DEMO_NOW.slice(0, 10);
  }
  Object.assign(deal, patch, { lastActivityAt: DEMO_NOW });
}

export async function approveBlurb(dealId: string, blurb: string) {
  const deal = db.deals.find((row) => row.id === dealId);
  if (!deal) return;
  deal.blurb = blurb;
  deal.blurbApprovedAt = DEMO_NOW.slice(0, 10);
}

// The engagement terms are passed to the skills and never stored on the deal,
// so no fee can reach a screen-shareable page (PRD P5).
export async function sendEngagementLetter(userId: UserId, dealId: string) {
  const deal = db.deals.find((row) => row.id === dealId);
  if (!deal) return;
  deal.lastActivityAt = DEMO_NOW;
  deal.nextStep = "Follow up on the engagement letter";
  logActivity(userId, `sent the engagement letter for ${deal.codeName}`);
}

// ---- Mandates ----

const MANDATE_FROM = STAGES.indexOf("Mandate signed");
// Apollo returns up to two contacts per company (PRD MB3); the demo invents them from this pool.
export const ENRICH_COST_CREDITS = 2;
const ENRICH_NAMES = ["Omar Rizk", "Sofia Marin", "Khalid Nasser", "Elena Petrova", "Tariq Aziz", "Maya Rahal"];

function addHistory(dealId: string, event: Omit<DealViewData["history"][number], "id" | "dealId" | "at">) {
  mdb.history.unshift({ id: `h-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, dealId, at: DEMO_NOW, ...event });
}

function touchDeal(dealId: string) {
  const deal = db.deals.find((row) => row.id === dealId);
  if (deal) deal.lastActivityAt = DEMO_NOW;
}


/** Every deal from Engaged on has its document cards; they start Not started. */
function ensureMaterials(deal: Deal) {
  if (STAGES.indexOf(deal.stage) >= STAGES.indexOf("Engaged") && !mdb.materials.some((row) => row.dealId === deal.id)) {
    mdb.materials.push(...mandateSeed.startingMaterials(deal.id, deal.side));
  }
}

export async function getDealView(dealId: string): Promise<DealViewData | null> {
  const deal = db.deals.find((row) => row.id === dealId);
  if (!deal) return null;
  ensureMaterials(deal);
  const forDeal = <T extends { dealId: string }>(rows: T[]) => rows.filter((row) => row.dealId === dealId);
  return structuredClone({
    now: DEMO_NOW,
    currentUserId: CURRENT_USER_ID,
    users: db.users,
    people: db.people,
    deal,
    // Deals without a recorded history still show the days in their current stage.
    details: mdb.details.find((row) => row.dealId === dealId) ?? { dealId, financials: { fy: "FY2025" }, stageEnteredAt: { [deal.stage]: optimizationSeed.stageEnteredAt[dealId] } },
    counterparties: forDeal(mdb.counterparties),
    suggestions: forDeal(mdb.suggestions),
    materials: forDeal(mdb.materials),
    offers: forDeal(mdb.offers).sort((a, b) => b.date.localeCompare(a.date)),
    history: forDeal(mdb.history).sort((a, b) => b.at.localeCompare(a.at)),
    apolloCreditsLeft: mdb.apolloCreditsLeft,
  });
}

export async function setNextStep(dealId: string, nextStep: string) {
  const deal = db.deals.find((row) => row.id === dealId);
  if (!deal) return;
  deal.nextStep = nextStep;
  touchDeal(dealId);
}

export async function updateCounterparty(userId: UserId, id: string, patch: { status?: CounterpartyStatus; nextStep?: string }) {
  const row = mdb.counterparties.find((item) => item.id === id);
  if (!row) return;
  if (patch.status && patch.status !== row.status) {
    addHistory(row.dealId, { type: "Buyer status", counterpartyId: id, text: `${row.name} moved to ${patch.status} by ${userName(userId)}.`, source: "Engine, written to Attio" });
  }
  Object.assign(row, patch);
  touchDeal(row.dealId);
}

export async function addSuggestions(dealId: string, ids: string[]) {
  const picked = mdb.suggestions.filter((row) => ids.includes(row.id));
  mdb.suggestions = mdb.suggestions.filter((row) => !ids.includes(row.id));
  for (const s of picked) {
    mdb.counterparties.push({ id: `c-${s.id}`, dealId, name: s.name, category: s.category, hq: s.hq, status: "Not contacted", contactIds: [], nextStep: "Enrich and send the teaser", rationale: s.rationale, website: s.website });
  }
  addHistory(dealId, { type: "Buyer status", text: `${picked.length} buyers added from Find more, not enriched.`, source: "Toolkit matching, written to Attio" });
}

export async function enrichCounterparty(id: string) {
  const row = mdb.counterparties.find((item) => item.id === id);
  if (!row || mdb.apolloCreditsLeft < ENRICH_COST_CREDITS) return;
  const free = ENRICH_NAMES.filter((name) => !db.people.some((person) => person.name === name)).slice(0, 2);
  for (const name of free) {
    const person = { id: `p-${Date.now()}-${name.split(" ")[0].toLowerCase()}`, name, org: row.name, role: "buyer" as const };
    db.people.push(person);
    row.contactIds.push(person.id);
  }
  mdb.apolloCreditsLeft -= ENRICH_COST_CREDITS;
  addHistory(row.dealId, { type: "Approval", counterpartyId: id, text: `Enriched ${row.name} with Apollo: ${free.length} contacts for ${ENRICH_COST_CREDITS} credits.`, source: "Apollo, approved in the Engine" });
}

export async function sendOutreach(id: string, contactId: string, template: string, link: string, summary: string) {
  const row = mdb.counterparties.find((item) => item.id === id);
  const contact = db.people.find((person) => person.id === contactId);
  if (!row || !contact) return;
  if (row.status === "Not contacted") row.status = "Contacted";
  row.lastContactAt = DEMO_NOW;
  // PRD R2: a first message starts the sequence (follow-ups at 4 and 9 working days);
  // a follow-up moves it one step. A reply, detected in Gmail, pauses it.
  if (!row.outreach || template !== "Follow-up") {
    row.outreach = { firstSentAt: DEMO_NOW.slice(0, 10), followUpsSent: 0, lastMessage: summary };
    row.nextStep = "Follow up in 4 working days if no reply";
  } else {
    row.outreach = { ...row.outreach, followUpsSent: row.outreach.followUpsSent + 1, lastMessage: summary };
    row.nextStep = row.outreach.followUpsSent >= 2 ? "Sequence done: decide whether to keep this name" : "Follow up again at 9 working days if no reply";
  }
  if (row.dealId) {
    addHistory(row.dealId, { type: "Email", counterpartyId: id, text: `${template} sent to ${contact.name}${link === "no link" ? "" : ` with ${link}`}.`, source: "Gmail, Sent; logged to Attio" });
    touchDeal(row.dealId);
  }
}

export async function getOutreach(userId: UserId): Promise<OutreachData> {
  const deals = db.deals.filter((deal) => deal.ownerId === userId);
  // Every counterparty on the user's deals plus the user's buyer and seller lists, except Passed.
  const rows = mdb.counterparties.filter((row) => row.status !== "Passed" && (row.listName || deals.some((deal) => deal.id === row.dealId)));
  return structuredClone({ now: DEMO_NOW, people: db.people, deals, rows, apolloCreditsLeft: mdb.apolloCreditsLeft });
}

export async function sendCim(dealId: string) {
  const signed = mdb.counterparties.filter((row) => row.dealId === dealId && row.ndaSignedDate && row.status !== "Passed");
  for (const row of signed) {
    row.lastContactAt = DEMO_NOW;
    row.nextStep = "Collect the first-round offer";
    addHistory(dealId, { type: "Email", counterpartyId: row.id, text: `CIM and data room invitation sent to ${row.name}.`, source: "Gmail, Sent; VantageKit invitation" });
  }
  await setNextStep(dealId, "Collect first-round offers");
}

export async function requestClientDocuments(dealId: string, items: string[]) {
  addHistory(dealId, { type: "Email", text: `Asked the client for ${items.length} missing items: ${items.join(", ")}.`, source: "Gmail, Sent" });
  touchDeal(dealId);
}

export async function setMaterialStatus(id: string, status: MaterialStatus) {
  const row = mdb.materials.find((item) => item.id === id);
  if (!row) return;
  row.status = status;
  row.date = DEMO_NOW.slice(0, 10);
  addHistory(row.dealId, { type: "Document", text: `${row.name}: ${status.toLowerCase()}.`, source: status === "Sent" ? "Gmail or DocuSign" : "Engine" });
}

export async function addOffer(dealId: string, input: OfferInput) {
  mdb.offers.push({ id: `o-${Date.now()}`, dealId, ...input });
  const buyer = mdb.counterparties.find((row) => row.id === input.counterpartyId);
  addHistory(dealId, { type: "Offer", counterpartyId: input.counterpartyId, text: `${input.type} from ${buyer?.name} saved: ${input.cashPct}% cash at close.`, source: input.documentName ? `Attachment ${input.documentName}` : "Entered by hand" });
}

export async function setOfferStatus(userId: UserId, id: string, status: OfferStatus, why: string) {
  const offer = mdb.offers.find((row) => row.id === id);
  if (!offer) return;
  offer.status = status;
  const buyer = mdb.counterparties.find((row) => row.id === offer.counterpartyId);
  const decided = status === "Accepted" || status === "Rejected";
  addHistory(offer.dealId, {
    type: decided ? "Decision" : "Offer",
    counterpartyId: offer.counterpartyId,
    text: `${buyer?.name} ${offer.type} marked ${status.toLowerCase()}.`,
    source: "Engine",
    decision: decided ? { who: userName(userId), why } : undefined,
  });
}

export async function logDecision(userId: UserId, dealId: string, text: string, why: string, counterpartyId?: string) {
  addHistory(dealId, { type: "Decision", counterpartyId, text, source: "Logged in the Engine", decision: { who: userName(userId), why } });
}

export async function emailClient(dealId: string, recipient: string) {
  addHistory(dealId, { type: "Email", text: `Update sent to ${recipient}.`, source: "Gmail, Sent" });
  touchDeal(dealId);
}

// ---- Buyers universe ----

export async function getBuyersUniverse(): Promise<BuyersUniverseData> {
  const deals = db.deals.filter((deal) => deal.side === "sell" && deal.status === "Active" && STAGES.indexOf(deal.stage) >= MANDATE_FROM);
  return structuredClone({ now: DEMO_NOW, users: db.users, people: db.people, buyers, deals, counterparties: mdb.counterparties.filter((row) => row.dealId), emails: emailLog });
}

/** Added by hand from the Buyers universe. Attio matches by website, so a known domain is not added twice. */
export async function addBuyer(userId: UserId, fields: Required<BuyerPatch> & Pick<BuyerRole, "name" | "hq" | "website">) {
  if (fields.website && inAttio(fields.website)) return;
  buyers.push({ ...fields, id: `br-${Date.now()}`, contactIds: [] });
  logActivity(userId, `added ${fields.name} to the buyers universe`);
}

export async function updateBuyer(userId: UserId, id: string, patch: BuyerPatch) {
  const buyer = buyers.find((row) => row.id === id);
  if (!buyer) return;
  Object.assign(buyer, patch);
  logActivity(userId, `updated ${buyer.name} in the buyers universe`);
}

/** Adds the buyer to a deal as a not contacted counterparty. Already on the deal: no change. */
export async function addBuyerToDeal(userId: UserId, buyerId: string, dealId: string) {
  const buyer = buyers.find((row) => row.id === buyerId);
  if (!buyer || mdb.counterparties.some((row) => row.dealId === dealId && row.name === buyer.name)) return;
  mdb.counterparties.push({
    id: `c-${buyerId}-${dealId}`,
    dealId,
    name: buyer.name,
    category: buyer.type === "Strategic" ? "Strategic" : "Financial",
    hq: buyer.hq,
    status: "Not contacted",
    contactIds: [...buyer.contactIds],
    nextStep: buyer.contactIds.length ? "Send the teaser" : "Enrich and send the teaser",
    rationale: buyer.notes,
    website: buyer.website,
  });
  addHistory(dealId, { type: "Buyer status", text: `${buyer.name} added from the buyers universe by ${userName(userId)}.`, source: "Engine, written to Attio" });
  touchDeal(dealId);
}

// ---- Buyers search ----

function freeCodeName() {
  return spareCodeNames.find((name) => !db.deals.some((deal) => deal.codeName === name)) ?? "Project New";
}

// Apollo returns up to two contacts per company; the demo invents them from this pool.
const SEARCH_CONTACT_NAMES = ["Aisha Karim", "Bilal Haddad", "Chloe Martin", "Dalia Nasr", "Ehab Saleh", "Fatima Zaki", "Ghassan Aoun", "Huda Salem", "Imran Sheikh", "Joelle Abi Nader", "Kamal Fares", "Laila Barakat"];
const SEARCH_CONTACT_TITLES = ["Head of M&A", "Investment Director"];

// Attio matches organizations by domain, so a domain already on a buyer role is never added twice (PRD S2).
const inAttio = (website: string) => buyers.some((buyer) => buyer.website === website);

/**
 * Toolkit matching plus Apollo company search. `filters` is null until the user clicks Search.
 * Keywords widen to any word (the filters do the narrowing); the live Toolkit ranks by meaning.
 */
export async function searchBuyers(filters: BuyerFilterValues | null, query: string): Promise<BuyersSearchData> {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const text = (c: (typeof candidates)[number]) => [c.name, c.rationale, ...c.sectors].join(" ").toLowerCase();
  const results = filters
    ? candidates.filter((c) => matchesFilters(c, filters) && (words.length === 0 || words.some((word) => text(c).includes(word)))).map((c) => ({ ...c, inAttio: inAttio(c.website) }))
    : null;
  return structuredClone({
    now: DEMO_NOW,
    results,
    profiles: [...buyers, ...candidates],
    people: db.people,
    deals: db.deals.filter((deal) => deal.side === "sell" && deal.status === "Active" && STAGES.indexOf(deal.stage) >= MANDATE_FROM),
    apolloCreditsLeft: mdb.apolloCreditsLeft,
    nextCodeName: freeCodeName(),
  });
}

/** Apollo contacts for each picked company not yet enriched. Stops when credits run out. */
// Buyers: the key contacts per run, more on a later run if needed. Sellers: the owner first.
export async function enrichCandidates(ids: string[]) {
  enrichCompanies(candidates, ids, "buyer", SEARCH_CONTACT_TITLES, 2, (website) => buyers.find((buyer) => buyer.website === website));
}

type Enrichable = { id: string; name: string; website: string; contactIds: string[]; enriched: boolean };

/**
 * Apollo contacts for each picked company not yet enriched, 2 credits each. Stops when credits run out.
 * A company already in Attio gets the contacts on its role too, so enriching after adding is not lost.
 */
function enrichCompanies(rows: Enrichable[], ids: string[], role: "buyer" | "other", titles: string[], perCompany: number, roleFor: (website: string) => { contactIds: string[] } | undefined) {
  for (const c of rows.filter((row) => ids.includes(row.id) && !row.enriched)) {
    if (mdb.apolloCreditsLeft < ENRICH_COST_CREDITS) return;
    const free = SEARCH_CONTACT_NAMES.filter((name) => !db.people.some((person) => person.name === name)).slice(0, perCompany);
    for (const [index, name] of free.entries()) {
      const person = { id: `p-${c.id}-${index}`, name, org: c.name, role, title: titles[index] };
      db.people.push(person);
      c.contactIds.push(person.id);
      const attioRole = roleFor(c.website);
      if (attioRole && attioRole.contactIds !== c.contactIds) attioRole.contactIds.push(person.id);
    }
    c.enriched = true;
    mdb.apolloCreditsLeft -= ENRICH_COST_CREDITS;
  }
}

/** Adds picked companies as Attio buyer roles. Domains already in Attio are skipped. Returns the buyer role ids. */
export async function addCandidatesAsBuyers(userId: UserId, ids: string[]) {
  const roleIds: string[] = [];
  for (const c of candidates.filter((row) => ids.includes(row.id))) {
    const existing = buyers.find((buyer) => buyer.website === c.website);
    if (existing) {
      roleIds.push(existing.id);
      continue;
    }
    const { id, source, rationale, enriched, ...profile } = c;
    buyers.push({ ...profile, id: `b-${id}`, ownerId: userId, status: "Active", contactIds: [...c.contactIds], notes: rationale });
    roleIds.push(`b-${id}`);
  }
  logActivity(userId, `added ${roleIds.length} buyers from Buyers search`);
  return roleIds;
}

/** Adds picked companies to a deal, first as buyer roles when they are not in Attio yet. */
export async function addCandidatesToDeal(userId: UserId, ids: string[], dealId: string) {
  for (const roleId of await addCandidatesAsBuyers(userId, ids)) await addBuyerToDeal(userId, roleId, dealId);
}

/** A buy-side lead in the Pipeline with the company as the prospective client. */
export async function createBuySideLead(userId: UserId, candidateId: string, codeName: string, sector: string, city: string) {
  const c = candidates.find((row) => row.id === candidateId);
  if (!c) return;
  db.deals.push({
    id: `d-${candidateId}`,
    codeName,
    clientName: c.name,
    side: "buy",
    stage: "Lead",
    status: "Active",
    ownerId: userId,
    sector,
    city,
    contactIds: [...c.contactIds],
    nextStep: "Book the first call to confirm their target criteria",
    lastActivityAt: DEMO_NOW,
    blurb: "",
  });
  logActivity(userId, `created ${codeName}, a buy-side lead for ${c.name}`);
}

// ---- Sellers universe ----

export async function getSellersUniverse(): Promise<SellersUniverseData> {
  const deals = db.deals.filter((deal) => deal.side === "buy" && deal.status === "Active" && STAGES.indexOf(deal.stage) >= MANDATE_FROM);
  return structuredClone({ now: DEMO_NOW, users: db.users, people: db.people, sellers, deals, counterparties: mdb.counterparties, nextCodeName: freeCodeName(), emails: emailLog });
}

export async function updateSeller(userId: UserId, id: string, patch: SellerPatch) {
  const seller = sellers.find((row) => row.id === id);
  if (!seller) return;
  Object.assign(seller, patch);
  logActivity(userId, `updated ${seller.name} in the sellers universe`);
}

/** Adds the seller as a not contacted target on a buy-side mandate. Already on the deal: no change. */
export async function addSellerToDeal(userId: UserId, sellerId: string, dealId: string) {
  const seller = sellers.find((row) => row.id === sellerId);
  if (!seller || mdb.counterparties.some((row) => row.dealId === dealId && row.name === seller.name)) return;
  mdb.counterparties.push({
    id: `c-${sellerId}-${dealId}`,
    dealId,
    name: seller.name,
    category: "Strategic",
    hq: seller.hq,
    status: "Not contacted",
    contactIds: [...seller.contactIds],
    nextStep: seller.contactIds.length ? "Ask the owner if open to selling" : "Find the owner's contact",
    rationale: seller.notes,
    website: seller.website,
  });
  addHistory(dealId, { type: "Buyer status", text: `${seller.name} added as a target from the sellers universe by ${userName(userId)}.`, source: "Engine, written to Attio" });
  touchDeal(dealId);
}

/** A sell-side lead in the Pipeline with the owner's company as the prospective client. */
export async function createSellSideLead(userId: UserId, sellerId: string, codeName: string, sector: string, city: string) {
  const seller = sellers.find((row) => row.id === sellerId);
  if (!seller) return;
  db.deals.push({
    id: `d-${sellerId}`,
    codeName,
    clientName: seller.name,
    side: "sell",
    stage: "Lead",
    status: "Active",
    ownerId: userId,
    sector,
    city,
    contactIds: [...seller.contactIds],
    nextStep: "Book the first call with the owner",
    lastActivityAt: DEMO_NOW,
    blurb: "",
  });
  logActivity(userId, `created ${codeName}, a sell-side lead for ${seller.name}`);
}

/**
 * PRD S3: sends the owner approach and starts follow-ups in Outreach. Reuses the seller's
 * list entry when there is one, so the Outreach tab shows one row per owner.
 */
export async function sendOwnerApproach(sellerId: string, contactId: string, summary: string) {
  const seller = sellers.find((row) => row.id === sellerId);
  if (!seller) return;
  let entry = mdb.counterparties.find((row) => row.listName && row.name === seller.name);
  if (!entry) {
    entry = { id: `l-${sellerId}`, dealId: "", listName: "Sellers: direct approach", name: seller.name, category: "Strategic", hq: seller.hq, status: "Not contacted", contactIds: [...seller.contactIds], nextStep: "Ask the owner if open to selling", rationale: seller.notes, website: seller.website };
    mdb.counterparties.push(entry);
  }
  // The list entry may predate the contact (found later in Sellers search).
  if (!entry.contactIds.includes(contactId)) entry.contactIds.push(contactId);
  await sendOutreach(entry.id, contactId, "Owner approach", "no link", summary);
}

// ---- Sellers search ----

const OWNER_TITLES = ["Founder and owner"];
const sellerRoleFor = (website: string) => sellers.find((seller) => seller.website === website);

/** Toolkit discovery plus Apollo company search. `filters` is null until the user clicks Search. */
export async function searchSellers(filters: SellerFilterValues | null, query: string): Promise<SellersSearchData> {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const text = (c: (typeof sellerFinds)[number]) => [c.name, c.rationale, c.sector].join(" ").toLowerCase();
  const results = filters
    ? sellerFinds
        .filter((c) => anyOf(filters.sector, [c.sector]) && anyOf(filters.geography, [c.geography]) && inRange(c.estRevenueUsd, filters.revenue))
        .filter((c) => (words.length === 0 || words.some((word) => text(c).includes(word))))
        .map((c) => {
          const role = sellerRoleFor(c.website);
          const approach = mdb.counterparties.find((row) => row.listName && row.name === c.name)?.outreach;
          return { ...c, inAttio: Boolean(role), contactIds: role ? role.contactIds : c.contactIds, approachedOn: approach?.firstSentAt };
        })
    : null;
  return structuredClone({
    now: DEMO_NOW,
    results,
    profiles: [...sellers, ...sellerFinds],
    people: db.people,
    deals: db.deals.filter((deal) => deal.side === "buy" && deal.status === "Active" && STAGES.indexOf(deal.stage) >= MANDATE_FROM),
    apolloCreditsLeft: mdb.apolloCreditsLeft,
    nextCodeName: freeCodeName(),
  });
}

export async function enrichSellerCandidates(ids: string[]) {
  enrichCompanies(sellerFinds, ids, "other", OWNER_TITLES, 1, sellerRoleFor);
}

/** Adds picked companies as Attio seller roles (open to selling: Unknown). Domains already in Attio are skipped. Returns the seller role ids. */
export async function addCandidatesAsSellers(userId: UserId, ids: string[]) {
  const roleIds: string[] = [];
  let added = 0;
  for (const c of sellerFinds.filter((row) => ids.includes(row.id))) {
    const existing = sellerRoleFor(c.website);
    if (existing) {
      roleIds.push(existing.id);
      continue;
    }
    added += 1;
    sellers.push({ id: `s-${c.id}`, name: c.name, hq: c.hq, website: c.website, sector: c.sector, geography: c.geography, estRevenueUsd: c.estRevenueUsd, openToSelling: "Unknown", ownerId: userId, contactIds: [...c.contactIds], notes: c.rationale });
    roleIds.push(`s-${c.id}`);
  }
  if (added) logActivity(userId, `added ${added} sellers from Sellers search`);
  return roleIds;
}

/** Adds picked companies as targets on a buy-side mandate, first as seller roles when new. */
export async function addSellerCandidatesToDeal(userId: UserId, ids: string[], dealId: string) {
  for (const roleId of await addCandidatesAsSellers(userId, ids)) await addSellerToDeal(userId, roleId, dealId);
}

export async function createSellSideLeadFromSearch(userId: UserId, candidateId: string, codeName: string, sector: string, city: string) {
  const [roleId] = await addCandidatesAsSellers(userId, [candidateId]);
  if (roleId) await createSellSideLead(userId, roleId, codeName, sector, city);
}

/** PRD S3: sends each reviewed owner note. New companies become seller roles first so follow-ups have a home. */
export async function sendOwnerApproaches(userId: UserId, notes: { id: string; contactId: string; summary: string }[]) {
  await addCandidatesAsSellers(userId, notes.map((note) => note.id));
  for (const note of notes) {
    const role = sellerRoleFor(sellerFinds.find((row) => row.id === note.id)?.website ?? "");
    if (role) await sendOwnerApproach(role.id, note.contactId, note.summary);
  }
}

// ---- Partners ----

export async function getPartners(): Promise<PartnersData> {
  return structuredClone({
    now: DEMO_NOW,
    currentUserId: CURRENT_USER_ID,
    users: db.users,
    partners: [...partnerRows].sort((a, b) => a.order - b.order),
    deals: db.deals.filter((deal) => deal.sourcePartnerId),
    nextCodeName: freeCodeName(),
  });
}

/**
 * PRD PA2: public fields go to Sanity, and the existing Sanity to Webflow sync updates the site.
 * Terms stay in the Engine database. Runs only on the person's Publish click.
 */
export async function publishPartner(userId: UserId, id: string, fields: PartnerPublic, terms: PartnerTerms) {
  if (id === "new") {
    partnerRows.push({ ...fields, id: `pa-${Date.now()}`, order: partnerRows.length + 1, terms, publishedAt: DEMO_NOW.slice(0, 10) });
    logActivity(userId, `added ${fields.name} as a referral partner`);
    return;
  }
  const partner = partnerRows.find((row) => row.id === id);
  if (!partner) return;
  Object.assign(partner, fields, { terms, publishedAt: DEMO_NOW.slice(0, 10) });
  logActivity(userId, `published ${partner.name} to the website`);
}

/** A lead the partner referred, in the Pipeline at Lead with the partner as source (PRD PA3). */
export async function createReferredLead(userId: UserId, partnerId: string, clientName: string, codeName: string, sector: string, city: string) {
  const partner = partnerRows.find((row) => row.id === partnerId);
  if (!partner) return;
  db.deals.push({ id: `d-ref-${Date.now()}`, codeName, clientName, side: "sell", stage: "Lead", status: "Active", ownerId: userId, sector, city, contactIds: [], nextStep: "Book the first call with the owner", lastActivityAt: DEMO_NOW, blurb: "", sourcePartnerId: partnerId });
  logActivity(userId, `logged ${codeName}, referred by ${partner.name}`);
}

// ---- Engine optimization ----

export async function getOptimization(): Promise<OptimizationData> {
  return structuredClone({
    now: DEMO_NOW,
    users: db.users,
    people: db.people,
    deals: db.deals,
    counterparties: mdb.counterparties,
    stageEnteredAt: optimizationSeed.stageEnteredAt,
    stageMedianDays: optimizationSeed.stageMedianDays,
    waitingClients: optimizationSeed.waitingClients,
    replyStats: optimizationSeed.replyStats,
    conversion: optimizationSeed.conversion,
    bottlenecks: [...bottleneckLog].sort((a, b) => b.at.localeCompare(a.at)),
  });
}

/** PRD EO2: anyone logs a bottleneck from any page. */
export async function logBottleneck(userId: UserId, what: string, where: string, dealId?: string) {
  bottleneckLog.push({ id: `bn-${Date.now()}`, at: DEMO_NOW, byId: userId, where, dealId: dealId || undefined, what, promoted: false });
}

/** Creates a Notion Issue from the bottleneck (EOS), on the person's click. */
export async function promoteBottleneck(id: string) {
  const row = bottleneckLog.find((item) => item.id === id);
  if (row) row.promoted = true;
}

// ---- Multiples ----

export async function getMultiples(): Promise<MultiplesData> {
  return structuredClone({ now: DEMO_NOW, currentUserName: userName(CURRENT_USER_ID), comparables: comparableRows });
}

/** PRD MU5: a reviewed web result joins the database with its source and the reviewer's name. */
export async function saveComparable(userId: UserId, id: string) {
  const row = comparableRows.find((item) => item.id === id);
  if (!row || row.verified) return;
  Object.assign(row, { verified: true, reviewer: userName(userId) });
  logActivity(userId, `saved ${row.target} to the multiples database`);
}

// ---- Skills ----

// Editing a skill needs admin rights (PRD ST1). Demo: Jules is the only admin.
const ADMINS: UserId[] = ["jules"];

export async function getSkills(): Promise<SkillsData> {
  return structuredClone({ now: DEMO_NOW, users: db.users, skills: skillRows, canEdit: ADMINS.includes(CURRENT_USER_ID) });
}

/** Saves a new version of the skill file. The Engine and Claude read the same file. */
export async function saveSkillVersion(userId: UserId, id: string, body: string, note: string) {
  const skill = skillRows.find((row) => row.id === id);
  if (!skill || !ADMINS.includes(userId)) return;
  const [major, minor] = skill.versions[0].version.split(".").map(Number);
  skill.body = body;
  skill.versions.unshift({ version: `${major}.${minor + 1}`, date: DEMO_NOW.slice(0, 10), byId: userId, note });
  logActivity(userId, `saved ${skill.title} version ${major}.${minor + 1}`);
}

// ---- Profile ----

export async function getProfile(): Promise<ProfileData> {
  return structuredClone({
    now: DEMO_NOW,
    user: db.users.find((user) => user.id === CURRENT_USER_ID)!,
    profile: profileRow,
    connections: connectionRows,
    available: connectorChoices,
  });
}

/** Connect or reconnect: once live this opens the provider's sign-in; the demo marks it connected. */
export async function connect(id: string) {
  const existing = connectionRows.find((row) => row.id === id);
  if (existing) {
    Object.assign(existing, { status: "Connected", lastSyncAt: DEMO_NOW, issue: undefined, account: existing.account || profileRow.whatsapp });
    return;
  }
  const choice = connectorChoices.find((row) => row.id === id);
  if (!choice) return;
  connectionRows.push({ ...choice, account: profileRow.email, status: "Connected", lastSyncAt: DEMO_NOW });
  connectorChoices = connectorChoices.filter((row) => row.id !== id);
}

// Email comes from Google sign-in and role and access are set by an admin, so only these three are yours to change.
export async function updateProfile(patch: Pick<Profile, "fullName" | "title" | "whatsapp">) {
  Object.assign(profileRow, patch);
}

export async function disconnect(id: string) {
  const row = connectionRows.find((item) => item.id === id);
  if (row) Object.assign(row, { status: "Not connected", lastSyncAt: undefined, issue: undefined });
}
