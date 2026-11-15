// Shapes mirror the tools of record (Attio, Gmail, Calendar, Notion, VantageKit)
// so each demo function can later return the Toolkit API response unchanged.
import type { NextAction } from "../lib/next-action";
import type { Stage } from "../lib/stages";

// Demo ids are first names; live ids are Attio user ids.
export type UserId = string;
// role decides what someone can do in the Engine (only advisors own deals); title is their job title.
export type User = { id: UserId; name: string; role: "Advisor" | "Analyst" | "Ops"; title: string };

export type PersonRole = "client" | "buyer" | "target" | "adviser" | "other";
export type Person = { id: string; name: string; org: string; role: PersonRole; title?: string; email?: string; phone?: string };

export const DEAL_STATUSES = ["Active", "On hold", "Passed"] as const;
export type DealStatus = (typeof DEAL_STATUSES)[number];

export type Deal = {
  id: string;
  codeName: string;
  clientName: string;
  side: "sell" | "buy";
  stage: Stage;
  status: DealStatus;
  ownerId: UserId;
  sector: string;
  city: string;
  /** Expected transaction value in USD. Never a fee. */
  valueUsd?: number;
  contactIds: string[];
  nextStep: string;
  lastActivityAt: string;
  /** The partner who referred this deal (PRD PA3). */
  sourcePartnerId?: string;
  /** Anonymised description for buyers (PRD P3). */
  blurb: string;
  blurbApprovedAt?: string;
  /** The client's legal details, needed for the client NDA. From Attio once live. */
  clientLegal?: ClientLegal;
};

export type ClientLegal = { name: string; jurisdiction: string; registration: string; address: string };

// ---- Mandates (Deal view) ----

/** Last full financial year, from Attio once gross profit and asking price are attributes. */
export type DealFinancials = { fy: string; revenueUsd?: number; grossProfitUsd?: number; ebitdaUsd?: number; askingPriceUsd?: number };

export type MandateDetails = {
  dealId: string;
  financials: DealFinancials;
  nextStepDue?: string;
  /** Date each stage was entered (Attio stage history); days per stage are computed from it. */
  stageEnteredAt: Partial<Record<Stage, string>>;
};

// Deal Room v1 merged buyer statuses, in sentence case.
export const COUNTERPARTY_STATUSES = [
  "Not contacted",
  "Contacted",
  "Initial conversations",
  "LOI",
  "Due diligence",
  "Bidding offer",
  "Closed",
  "Passed",
] as const;
export type CounterpartyStatus = (typeof COUNTERPARTY_STATUSES)[number];

export type Counterparty = {
  id: string;
  dealId: string;
  name: string;
  category: "Strategic" | "Financial";
  hq: string;
  status: CounterpartyStatus;
  ndaSignedDate?: string;
  /** Contacts already in Attio (PRD MB3). Each enrichment can add more. */
  contactIds: string[];
  lastContactAt?: string;
  nextStep: string;
  rationale: string;
  website: string;
  dataRoom?: { lastViewAt: string; filesOpened: number };
  /** Set for buyer or seller list entries not yet on a deal (dealId is then ""). */
  listName?: string;
  /** The outreach sequence: first message, follow-ups sent, reply (PRD R1, R2). */
  outreach?: { firstSentAt: string; followUpsSent: number; repliedAt?: string; lastMessage: string };
};

/** A company found by Find more, added unenriched (PRD MB2). */
export type Suggestion = { id: string; dealId: string; name: string; category: "Strategic" | "Financial"; hq: string; rationale: string; website: string };

// PRD MM1 to MM5: one card per document the deal needs, in the order the deal needs them.
export const MATERIAL_NAMES = ["Proposal", "Client NDA", "Engagement contract", "Financials", "Teaser", "CIM", "Data room"] as const;
export type MaterialName = (typeof MATERIAL_NAMES)[number];
/** Agreements are signed; documents are drafted then approved; the data room goes live in VantageKit. */
export const MATERIAL_STATUSES = ["Not started", "Drafted", "Sent", "Signed", "Approved", "Live"] as const;
export type MaterialStatus = (typeof MATERIAL_STATUSES)[number];
/** One thing the document needs. "client" items are asked for by email; "us" items are prepared by the team. */
export type MaterialItem = { name: string; why: string; from: "client" | "us"; have: boolean };
export type Material = {
  id: string;
  dealId: string;
  name: MaterialName;
  /** The Wusool skill Claude uses to draft it; none for the data room. */
  skill?: string;
  status: MaterialStatus;
  date?: string;
  version?: string;
  items: MaterialItem[];
  mainTerms: string[];
  /** Hidden until "Show terms" is clicked, so the page is safe to screen-share (PRD MM5). */
  feeTerms: string[];
};

export const OFFER_STATUSES = ["Received", "Sent", "Under review", "Accepted", "Rejected"] as const;
export type OfferStatus = (typeof OFFER_STATUSES)[number];
export type Offer = {
  id: string;
  dealId: string;
  counterpartyId: string;
  type: "IOI" | "LOI";
  date: string;
  evUsd: number;
  cashPct: number;
  deferredPct: number;
  earnoutPct: number;
  conditions: string;
  ddWeeks: number;
  exclusivityWeeks: number;
  status: OfferStatus;
  documentName?: string;
};
export type OfferInput = Omit<Offer, "id" | "dealId">;

export const HISTORY_TYPES = ["Email", "WhatsApp", "Meeting", "Stage", "Buyer status", "Document", "Offer", "Approval", "Decision"] as const;
export type HistoryType = (typeof HISTORY_TYPES)[number];
export type HistoryEvent = {
  id: string;
  dealId: string;
  at: string;
  type: HistoryType;
  counterpartyId?: string;
  text: string;
  /** Where the event comes from; every event links to its source (PRD MH3). */
  source: string;
  decision?: { who: string; why: string };
};

export type DealCounts = { buyersInPlay: number; ndasSigned: number; offers: number };

export type OutreachData = {
  now: string;
  people: Person[];
  /** Deals the user owns, for code names and the codename check. */
  deals: Deal[];
  rows: Counterparty[];
  apolloCreditsLeft: number;
};


export type DealViewData = {
  now: string;
  currentUserId: UserId;
  users: User[];
  people: Person[];
  deal: Deal;
  details: MandateDetails;
  counterparties: Counterparty[];
  suggestions: Suggestion[];
  materials: Material[];
  offers: Offer[];
  history: HistoryEvent[];
  apolloCreditsLeft: number;
};

// ---- Buyers universe (Attio buyer_roles, PRD U1) ----

export const BUYER_TYPES = ["Strategic", "Private equity", "Family office"] as const;
export type BuyerType = (typeof BUYER_TYPES)[number];
export const BUYER_STATUSES = ["Active", "Dormant", "Do not contact"] as const;
export type BuyerStatus = (typeof BUYER_STATUSES)[number];

export type BuyerRole = {
  id: string;
  name: string;
  /** Null while no source column holds it (live mode); shown as a dash. */
  type: BuyerType | null;
  hq: string;
  website: string;
  sectors: string[];
  geographies: string[];
  // Attio stores these in AED; the Toolkit converts at the 3.6725 peg so the Engine shows USD only.
  /** Attio buyer_role.check_size_min and _max: what the buyer pays per deal. */
  checkSizeMinUsd: number | null;
  checkSizeMaxUsd: number | null;
  /** Attio buyer_role.ebitda_floor: the smallest target EBITDA the buyer looks at. */
  ebitdaFloorUsd: number | null;
  ownerId: UserId | null;
  /** The demo uses BUYER_STATUSES; live shows Attio's mandate status. */
  status: string | null;
  /** First is the key contact. */
  contactIds: string[];
  notes: string;
  /** Live only: the version the edit is checked against. */
  etag?: string;
};

/** Fields editable from the buyer drawer; written back to Attio. */
export type BuyerPatch = Partial<Pick<BuyerRole, "type" | "sectors" | "geographies" | "checkSizeMinUsd" | "checkSizeMaxUsd" | "ebitdaFloorUsd" | "ownerId" | "status" | "notes">>;

export type BuyersUniverseData = {
  now: string;
  users: User[];
  people: Person[];
  buyers: BuyerRole[];
  /** Active sell-side mandates a buyer can be added to. */
  deals: Deal[];
  /** Deal counterparty rows, matched to buyers by name for the deal history. */
  counterparties: Counterparty[];
  emails: EmailLogEntry[];
  /** Rows under the filters and search; `total` counts every buyer. */
  matched: number;
  total: number;
  /** Set when more rows match than this page holds. */
  nextCursor: string | null;
  /** Choices for the filters and the edit form, across every buyer. */
  options: { sectors: string[]; geographies: string[]; statuses: string[] };
  /** Blocks whose connector is not live yet; they come back empty. */
  unavailable: string[];
};

/** One Gmail thread with a company: subject and date only (Gmail keeps the messages). */
export type EmailLogEntry = { id: string; org: string; subject: string; date: string };

// ---- Sellers universe (Attio seller_roles, PRD U1) ----

// Attio seller_role.appetite_signal (No signal, Interest, Warm intro), shown in plain words.
export const OPEN_TO_SELLING = ["Unknown", "Interested", "Warm intro"] as const;
export type OpenToSelling = (typeof OPEN_TO_SELLING)[number];

export type SellerRole = {
  id: string;
  name: string;
  hq: string;
  website: string;
  sector: string;
  geography: string;
  /** Attio seller_role.est_revenue and est_ebitda, converted from AED by the Toolkit. */
  estRevenueUsd: number | null;
  /** Unknown for owners found in Sellers search until someone fills it in. */
  estEbitdaUsd?: number;
  openToSelling: OpenToSelling;
  /** Attio seller_role.re_engage_date: when to approach the owner again. */
  reEngageDate?: string;
  ownerId: UserId | null;
  /** First is the owner contact. */
  contactIds: string[];
  notes: string;
  /** Live only: the version the edit is checked against. */
  etag?: string;
};

/** A missing key means unchanged, so clearing the EBITDA or the re-engage date sends null. */
export type SellerPatch = Partial<Pick<SellerRole, "sector" | "geography" | "estRevenueUsd" | "openToSelling" | "ownerId" | "notes">> & {
  estEbitdaUsd?: number | null;
  reEngageDate?: string | null;
};

export type SellersUniverseData = {
  now: string;
  users: User[];
  people: Person[];
  sellers: SellerRole[];
  /** Active buy-side mandates a seller can be added to as a target. */
  deals: Deal[];
  /** Deal targets and seller list entries, matched to sellers by name. */
  counterparties: Counterparty[];
  /** A free code name for a new sell-side lead. */
  nextCodeName: string;
  emails: EmailLogEntry[];
  matched: number;
  total: number;
  nextCursor: string | null;
  options: { sectors: string[]; geographies: string[] };
  unavailable: string[];
};

// ---- Sellers search (PRD S1 to S3) ----

/** A company from Toolkit discovery or Apollo company search. Apollo gives revenue, rarely EBITDA. */
export type SellerCandidate = Pick<SellerRole, "name" | "hq" | "website" | "sector" | "geography" | "estRevenueUsd"> & {
  id: string;
  employees: number;
  source: "Wusool database" | "Apollo";
  rationale: string;
  /** Owner contacts: filled by Apollo enrichment, or the seller role's when already in Attio. */
  contactIds: string[];
  enriched: boolean;
};

export type SellerResult = SellerCandidate & {
  inAttio: boolean;
  /** Date of the first owner approach, when the owner was already asked. */
  approachedOn?: string;
};

export type SellersSearchData = {
  now: string;
  /** Null until the user clicks Search. */
  results: SellerResult[] | null;
  /** Every searchable profile, for the filter options. */
  profiles: Pick<SellerRole, "sector" | "geography">[];
  people: Person[];
  /** Active buy-side mandates a seller can be added to as a target. */
  deals: Deal[];
  apolloCreditsLeft: number;
  nextCodeName: string;
};

// ---- Buyers search (PRD S1, S2) ----

/** A company returned by Toolkit matching or Apollo company search. */
export type BuyerCandidate = Pick<BuyerRole, "name" | "type" | "hq" | "website" | "sectors" | "geographies" | "checkSizeMinUsd" | "checkSizeMaxUsd" | "ebitdaFloorUsd"> & {
  id: string;
  source: "Wusool database" | "Apollo";
  rationale: string;
  /** Filled by Apollo enrichment. */
  contactIds: string[];
  enriched: boolean;
};

/** A candidate as shown in results: matched to Attio by domain. */
export type BuyerResult = BuyerCandidate & { inAttio: boolean };

export type BuyersSearchData = {
  now: string;
  /** Null until the user clicks Search. */
  results: BuyerResult[] | null;
  /** Every searchable profile, for the filter options. */
  profiles: Pick<BuyerRole, "sectors" | "geographies" | "type" | "checkSizeMinUsd" | "checkSizeMaxUsd" | "ebitdaFloorUsd">[];
  people: Person[];
  deals: Deal[];
  apolloCreditsLeft: number;
  /** A free code name for a new buy-side lead. */
  nextCodeName: string;
};

/** Fields editable from the Pipeline quick view. */
export type DealPatch = Partial<Pick<Deal, "stage" | "status" | "ownerId" | "valueUsd" | "contactIds" | "nextStep">>;

export type Task = { id: string; ownerId: UserId; title: string; dueDate: string; dealId?: string; done: boolean };

export type DraftTask = { title: string; dueDate: string };

type PendingBase = { id: string; ownerId: UserId; title: string; source: string };

export type PendingItem =
  | (PendingBase & { kind: "email"; dealId?: string; toId: string; body: string })
  /** A follow-up the reminder rule raised. The draft is written only when someone clicks Generate email. */
  | (PendingBase & { kind: "follow-up"; dealId?: string; toId: string; reason: string; body: string })
  | (PendingBase & { kind: "stage-change"; dealId: string; toStage: Stage; evidence: string })
  | (PendingBase & { kind: "tasks"; dealId?: string; tasks: DraftTask[] })
  | (PendingBase & { kind: "next-step"; dealId: string; nextStep: string });

/** Fields a person may change before approving a pending item. */
export type PendingEdit = { body?: string; toStage?: Stage; tasks?: DraftTask[]; nextStep?: string };

export type ActionEmail = {
  id: string;
  ownerId: UserId;
  fromId: string;
  subject: string;
  receivedAt: string;
  dealId?: string;
  message: string;
  suggestedAction: string;
  draftReply: string;
};

export const WORKSTREAM_STATUSES = ["Not started", "In progress", "Blocked", "Done"] as const;
export type WorkstreamStatus = (typeof WORKSTREAM_STATUSES)[number];
export type Workstream = {
  id: string;
  ownerId: UserId;
  name: string;
  status: WorkstreamStatus;
  nextStep: string;
  dueDate: string;
  linkedTo: string;
};

export type Meeting = {
  kind: "meeting";
  id: string;
  ownerId: UserId;
  title: string;
  start: string;
  end: string;
  dealId?: string;
  attendeeIds: string[];
  recent: { date: string; text: string }[];
};
export type Deadline = { kind: "deadline"; id: string; ownerId: UserId; title: string; date: string; dealId?: string };
export type AgendaItem = Meeting | Deadline;

/** Like the Attio "Met" fields: the actual is the number of people tagged this week. */
/** "count" metrics count the people tagged on them, like the Attio "Met" fields; "yes-no" is one switch a week. */
export type ScorecardMetric = { id: string; label: string; kind: "count" | "yes-no"; target: number; taggedIds: string[]; done?: boolean };
export type ScorecardMetricInput = Pick<ScorecardMetric, "id" | "label" | "kind" | "target">;
export type Scorecard = {
  ownerId: UserId;
  weekOf: string;
  workdaysElapsed: number;
  metrics: ScorecardMetric[];
  /** Attendees from this week's calendar, offered as one-click tags. */
  suggestedPersonIds: string[];
};

// ---- Profile ----

export type Profile = { fullName: string; title: string; email: string; whatsapp: string; admin: boolean };

export const CONNECTION_STATUSES = ["Connected", "Needs attention", "Not connected"] as const;
export type ConnectionStatus = (typeof CONNECTION_STATUSES)[number];
export type Connection = {
  id: string;
  name: string;
  /** What the Engine uses it for, in plain words. */
  purpose: string;
  account: string;
  status: ConnectionStatus;
  lastSyncAt?: string;
  /** Why it needs attention. */
  issue?: string;
};

export type ProfileData = {
  now: string;
  user: User;
  profile: Profile;
  connections: Connection[];
  available: Pick<Connection, "id" | "name" | "purpose">[];
};

// ---- Skills (PRD ST1) ----

export type SkillVersion = { version: string; date: string; byId: UserId; note: string };

export type Skill = {
  id: string;
  /** The skill file's name, the same one Claude loads. */
  name: string;
  title: string;
  category: "Contract" | "Proposal" | "NDA" | "Email" | "Invoice" | "Teaser" | "CIM";
  file: string;
  /** Where the Engine uses it. */
  usedIn: string[];
  body: string;
  /** Newest first. */
  versions: SkillVersion[];
};

export type SkillsData = { now: string; users: User[]; skills: Skill[]; canEdit: boolean };

// ---- Multiples (PRD MU1 to MU7) ----

export type Comparable = {
  id: string;
  target: string;
  acquirer: string;
  sector: string;
  geography: string;
  date: string;
  /** Enterprise value. */
  sizeUsd: number;
  type: "Strategic" | "Sponsor";
  evEbitda: number;
  evRevenue: number;
  /** Where the number comes from; every row carries one (MU3). A link for web rows. */
  source: string;
  /** Database rows only: who reviewed it. Web rows are unverified until saved (MU5). */
  reviewer?: string;
  verified: boolean;
};

export type MultiplesData = { now: string; currentUserName: string; comparables: Comparable[] };

// ---- Engine optimization (PRD EO1 to EO3) ----

export type WaitingClient = { id: string; dealId: string; personId: string; subject: string; lastFromClientAt: string };
export type ReplyStat = { template: string; sector: string; sent: number; replied: number };
export type ConversionRow = { stage: string; reached: number; advanced: number };
export type Bottleneck = { id: string; at: string; byId: UserId; where: string; dealId?: string; what: string; promoted: boolean };

export type OptimizationData = {
  now: string;
  users: User[];
  people: Person[];
  deals: Deal[];
  /** Every deal counterparty and list entry, for missed follow-ups. */
  counterparties: Counterparty[];
  stageEnteredAt: Record<string, string>;
  stageMedianDays: Record<string, number>;
  waitingClients: WaitingClient[];
  replyStats: ReplyStat[];
  conversion: ConversionRow[];
  bottlenecks: Bottleneck[];
};

// ---- Partners (PRD PA1 to PA3) ----

/** Public fields: the website's Sanity `partner` document. */
export type PartnerPublic = {
  name: string;
  category: string;
  description: string;
  offer: string;
  referralType: "Code" | "Link";
  referral: string;
  url: string;
  locations: string[];
  companySizes: string[];
  active: boolean;
};

/** Internal terms live in the Engine database, never in Sanity (not public). */
export type PartnerTerms = { commission: string; agreement: string; contactName: string; contactEmail: string };

export type Partner = PartnerPublic & { id: string; order: number; terms: PartnerTerms; publishedAt: string };

export type PartnersData = { now: string; currentUserId: UserId; users: User[]; partners: Partner[]; deals: Deal[]; nextCodeName: string };

/** One finished week of a scorecard: the actual per metric id (PRD K2). */
export type ScorecardWeek = { ownerId: UserId; weekOf: string; actuals: Record<string, number> };

export type ScorecardsData = {
  now: string;
  currentUserId: UserId;
  users: User[];
  people: Person[];
  scorecards: Scorecard[];
  history: ScorecardWeek[];
};

export type DataRoomEvent = { id: string; dealId: string; at: string; text: string };
export type ActivityEvent = { id: string; at: string; actorId: UserId; text: string };
export type Brief = { ownerId: UserId; sentAt: string; bullets: string[] };
export type ToolTabAnswer = { date: string; tools: string[] };

export type PipelineData = {
  now: string;
  currentUserId: UserId;
  users: User[];
  people: Person[];
  deals: Deal[];
  counts: Record<string, DealCounts>;
  /** Seller roles (sell-side clients) and buyer roles (buy-side clients) already in Attio, for New deal. */
  clients: ClientChoice[];
  nextCodeName: string;
  /** The one next thing to do on each deal, by deal id (from `lib/next-action.ts`). */
  nextActions: Record<string, NextAction>;
};

export type ClientChoice = { id: string; side: "sell" | "buy"; name: string; sector: string; city: string };
/** New deal: an existing role by id, or a new company that becomes a role in Attio. */
export type NewDealInput = { side: "sell" | "buy"; roleId?: string; newName?: string; codeName: string; sector: string; city: string };

export type HomeData = {
  now: string;
  user: User;
  users: User[];
  brief: Brief;
  pendingItems: PendingItem[];
  emails: ActionEmail[];
  workstreams: Workstream[];
  mandates: Deal[];
  deals: Deal[];
  people: Person[];
  agenda: AgendaItem[];
  scorecard: Scorecard;
  dataRoom: DataRoomEvent[];
  activity: ActivityEvent[];
  toolTabAnswer: ToolTabAnswer | null;
};
