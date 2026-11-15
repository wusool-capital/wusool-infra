// Invented demo data. No real client, buyer or number. Staff first names only.
// "Now" is fixed so overdue items and scorecard pace stay the same on every visit.
import type {
  ActionEmail,
  ActivityEvent,
  AgendaItem,
  Brief,
  DataRoomEvent,
  Deal,
  PendingItem,
  Person,
  Scorecard,
  Task,
  ToolTabAnswer,
  User,
  UserId,
  Workstream,
} from "./types";

export const DEMO_NOW = "2026-11-11T08:40:00+04:00";

const users: User[] = [
  { id: "jules", name: "Jules", role: "Advisor", title: "Co-founder and COO" },
  { id: "hugo", name: "Hugo", role: "Advisor", title: "Co-founder and CEO" },
  { id: "ramzy", name: "Ramzy", role: "Advisor", title: "Associate" },
  { id: "maria", name: "Maria", role: "Ops", title: "Operations" },
];

const people: Person[] = [
  { id: "p-omar", name: "Omar Khalil", org: "Dunewell Veterinary Clinics", role: "client", title: "Founder and CEO", email: "omar@dunewellvet.example", phone: "+971 50 111 2040" },
  { id: "p-karim", name: "Karim Aziz", org: "Ivorybay Dental", role: "client", title: "Managing partner", email: "karim@ivorybay.example", phone: "+966 55 230 4415" },
  { id: "p-priya", name: "Priya Menon", org: "Harbourline Family Office", role: "client", title: "Investment director", email: "priya@harbourline.example", phone: "+971 52 418 9902" },
  { id: "p-nadia", name: "Nadia Farouk", org: "Farouk & Co Accountants", role: "adviser" },
  { id: "p-layla", name: "Layla Haddad", org: "Arcadia Pet Ventures", role: "buyer", title: "Head of M&A" },
  { id: "p-sara", name: "Sara Nasser", org: "Gulfstone Partners", role: "buyer", title: "Partner" },
  { id: "p-daniel", name: "Daniel Reyes", org: "Oasis Growth Fund", role: "buyer", title: "Investment Director" },
  { id: "p-youssef", name: "Youssef Saleh", org: "Meridian Health Holdings", role: "buyer", title: "Chief Strategy Officer" },
  { id: "p-faisal", name: "Faisal Rahman", org: "Sandcrest Freight", role: "target", title: "Founder and CEO" },
  { id: "p-tom", name: "Tom Becker", org: "Sandbar Capital", role: "other" },
  { id: "p-hessa", name: "Hessa Al Marri", org: "Bluegate Advisory", role: "other" },
  { id: "p-rami", name: "Rami Toma", org: "Northstar Logistics", role: "other", title: "Owner and managing director" },
  { id: "p-rania", name: "Rania Saad", org: "Kestrel Security Services", role: "client", title: "Founder and owner", email: "rania@kestrelsecurity.example", phone: "+971 56 702 3318" },
  { id: "p-hamad", name: "Hamad Saeed", org: "Brewline Roasters", role: "client", title: "Co-founder", email: "hamad@brewline.example", phone: "+971 50 966 1207" },
];

const deals: Deal[] = [
  { id: "d-falcon", codeName: "Project Falcon", clientName: "Dunewell Veterinary Clinics", side: "sell", stage: "Outreach", status: "Active", ownerId: "jules", sector: "Veterinary clinics", city: "Dubai", valueUsd: 14_500_000, contactIds: ["p-omar"], nextStep: "Send the CIM to the 3 buyers who signed the NDA", lastActivityAt: "2026-11-11T07:52:00+04:00", blurb: "A group of six veterinary clinics in Dubai with 18 vets and a loyal client base. Revenue has grown every year since 2022, led by surgery and wellness plans. The founder wants a full sale and will support a 12-month transition.", blurbApprovedAt: "2026-10-30", clientLegal: { name: "Dunewell Veterinary Clinics LLC", jurisdiction: "Dubai, UAE", registration: "DED 1184520", address: "Al Wasl Road, Jumeirah 2, Dubai, UAE" } },
  { id: "d-pearl", codeName: "Project Pearl", clientName: "Ivorybay Dental", side: "sell", stage: "Non-binding offers", status: "Active", ownerId: "jules", sector: "Dental clinics", city: "Riyadh", valueUsd: 9_800_000, contactIds: ["p-karim"], nextStep: "Open the data room to Meridian Health", lastActivityAt: "2026-11-10T14:05:00+04:00", blurb: "Four dental clinics in Riyadh with an in-house lab and long-term insurer contracts. Patient volumes are steady and margins sit above the market average. The owners seek a majority sale to a healthcare group.", blurbApprovedAt: "2026-09-21" },
  { id: "d-cedar", codeName: "Project Cedar", clientName: "Brewline Roasters", side: "sell", stage: "Preparation", status: "Active", ownerId: "jules", sector: "Specialty coffee", city: "Abu Dhabi", valueUsd: 6_200_000, contactIds: ["p-hamad", "p-nadia"], nextStep: "Finish the teaser for client approval", lastActivityAt: "2026-11-10T16:05:00+04:00", blurb: "A specialty coffee roaster in Abu Dhabi supplying 140 cafes and hotels, with a growing online subscription business. The owner wants a full sale within 9 months.", clientLegal: { name: "Brewline Roasters LLC", jurisdiction: "Abu Dhabi, UAE", registration: "CN-3301872", address: "Musaffah M-14, Abu Dhabi, UAE" } },
  { id: "d-atlas", codeName: "Project Atlas", clientName: "Harbourline Family Office", side: "buy", stage: "Non-binding offers", status: "Active", ownerId: "jules", sector: "Logistics", city: "KSA and UAE", valueUsd: 25_000_000, contactIds: ["p-priya"], nextStep: "Agree LOI terms for Sandcrest Freight", lastActivityAt: "2026-11-10T18:20:00+04:00", blurb: "" },
  { id: "d-onyx", codeName: "Project Onyx", clientName: "Kestrel Security Services", side: "sell", stage: "Engaged", status: "Active", ownerId: "jules", sector: "Security services", city: "Dubai", valueUsd: 7_500_000, contactIds: ["p-rania"], nextStep: "Send the engagement letter", lastActivityAt: "2026-11-09T15:30:00+04:00", blurb: "A manned guarding and security systems company in Dubai with 420 staff and multi-year contracts with property managers. Revenue is recurring and the founder plans to retire after a 6-month handover.", clientLegal: { name: "Kestrel Security Services LLC", jurisdiction: "Dubai, UAE", registration: "DED 905317", address: "Office 1204, Al Quoz Industrial 3, Dubai, UAE" } },
  { id: "d-quartz", codeName: "Project Quartz", clientName: "Vertex Fit Clubs", side: "sell", stage: "Lead", status: "Active", ownerId: "jules", sector: "Fitness clubs", city: "Dubai", valueUsd: 4_000_000, contactIds: [], nextStep: "Book the first call with the owner", lastActivityAt: "2026-11-06T11:00:00+04:00", blurb: "", clientLegal: { name: "Vertex Fit Clubs FZ-LLC", jurisdiction: "Dubai, UAE", registration: "", address: "" } },
  { id: "d-lotus", codeName: "Project Lotus", clientName: "Greenleaf Pharmacies", side: "sell", stage: "Qualified", status: "Passed", ownerId: "jules", sector: "Pharmacy retail", city: "Riyadh", contactIds: [], nextStep: "None: owner price expectation too high", lastActivityAt: "2026-10-22T10:00:00+04:00", blurb: "" },
  { id: "d-dune", codeName: "Project Dune", clientName: "Clearspan Facilities", side: "sell", stage: "Mandate signed", status: "Active", ownerId: "hugo", sector: "Facility management", city: "Dubai", valueUsd: 11_000_000, contactIds: [], nextStep: "Collect 3 years of financials", lastActivityAt: "2026-11-11T08:20:00+04:00", blurb: "" },
  { id: "d-mirage", codeName: "Project Mirage", clientName: "Sunline Travel", side: "sell", stage: "Closing", status: "Active", ownerId: "hugo", sector: "Travel services", city: "Dubai", valueUsd: 18_000_000, contactIds: [], nextStep: "Agree the funds flow with both lawyers", lastActivityAt: "2026-11-10T12:10:00+04:00", blurb: "" },
  { id: "d-juniper", codeName: "Project Juniper", clientName: "Alder Capital", side: "buy", stage: "Lead", status: "Active", ownerId: "hugo", sector: "Healthcare clinics", city: "UAE", contactIds: [], nextStep: "Confirm the target criteria", lastActivityAt: "2026-11-04T09:45:00+04:00", blurb: "" },
  { id: "d-amber", codeName: "Project Amber", clientName: "Northgate Labs", side: "sell", stage: "Preparation", status: "On hold", ownerId: "hugo", sector: "Diagnostic labs", city: "Sharjah", valueUsd: 8_200_000, contactIds: [], nextStep: "Wait for the licence renewal", lastActivityAt: "2026-10-28T14:00:00+04:00", blurb: "" },
  { id: "d-orbit", codeName: "Project Orbit", clientName: "Northwind Holdings", side: "buy", stage: "Qualified", status: "Active", ownerId: "ramzy", sector: "HR software", city: "Riyadh", valueUsd: 30_000_000, contactIds: [], nextStep: "Send the buy-side proposal", lastActivityAt: "2026-11-10T16:30:00+04:00", blurb: "" },
  { id: "d-saffron", codeName: "Project Saffron", clientName: "Tamra Foods", side: "sell", stage: "Due diligence", status: "Active", ownerId: "ramzy", sector: "Food manufacturing", city: "Sharjah", valueUsd: 12_000_000, contactIds: [], nextStep: "Answer the buyer's tax questions", lastActivityAt: "2026-11-09T17:20:00+04:00", blurb: "" },
  { id: "d-coral", codeName: "Project Coral", clientName: "Bayview Schools", side: "sell", stage: "Closed", status: "Active", ownerId: "ramzy", sector: "Education", city: "Abu Dhabi", valueUsd: 22_000_000, contactIds: [], nextStep: "Send the closing invoice", lastActivityAt: "2026-11-02T10:00:00+04:00", blurb: "" },
];

const tasks: Task[] = [
  { id: "t-1", ownerId: "jules", title: "Send the NDA to Oasis Growth Fund", dueDate: "2026-11-09", dealId: "d-falcon", done: false },
  { id: "t-2", ownerId: "jules", title: "Chase Ivorybay for the lease agreements", dueDate: "2026-11-10", dealId: "d-pearl", done: false },
  { id: "t-3", ownerId: "jules", title: "Review the Cedar teaser draft", dueDate: "2026-11-11", dealId: "d-cedar", done: false },
  { id: "t-4", ownerId: "jules", title: "Prepare 5 target profiles for Harbourline", dueDate: "2026-11-11", dealId: "d-atlas", done: false },
  { id: "t-5", ownerId: "jules", title: "Send the CIM to signed buyers", dueDate: "2026-11-12", dealId: "d-falcon", done: false },
  { id: "t-6", ownerId: "jules", title: "Collect the cap table from Brewline", dueDate: "2026-11-13", dealId: "d-cedar", done: false },
  { id: "t-7", ownerId: "jules", title: "Update the scorecard before the team meeting", dueDate: "2026-11-13", done: false },
];

const pendingItems: PendingItem[] = [
  {
    id: "r-1",
    ownerId: "jules",
    kind: "stage-change",
    title: "Move Project Pearl to Due diligence",
    dealId: "d-pearl",
    toStage: "Due diligence",
    evidence: "Youssef Saleh sent the signed LOI from Meridian Health Holdings on 10 Nov 2026.",
    source: "Email from Youssef Saleh, 10 Nov 2026",
  },
  {
    id: "r-2",
    ownerId: "jules",
    kind: "follow-up",
    title: "Follow-up to Gulfstone Partners",
    reason: "Teaser sent on 5 Nov 2026. No reply after 4 working days.",
    dealId: "d-falcon",
    toId: "p-sara",
    body: "Dear Sara,\n\nI am following up on the Project Falcon teaser we shared on 5 Nov. The business is a multi-site veterinary group in Dubai with steady growth over the last three years.\n\nIf it fits your mandate, I can send the NDA today so you can read the CIM.\n\nBest regards,\nJules",
    source: "Follow-up reminder, 4 working days after the teaser",
  },
  {
    id: "r-3",
    ownerId: "jules",
    kind: "tasks",
    title: "3 tasks from your call with Omar Khalil",
    dealId: "d-falcon",
    tasks: [
      { title: "Send Omar the buyer shortlist", dueDate: "2026-11-12" },
      { title: "Ask Dunewell for the 2025 audited accounts", dueDate: "2026-11-13" },
      { title: "Book the site visit for Oasis Growth Fund", dueDate: "2026-11-17" },
    ],
    source: "Scribe note, 10 Nov 2026",
  },
  {
    id: "r-4",
    ownerId: "jules",
    kind: "next-step",
    title: "Update the next step on Project Cedar",
    dealId: "d-cedar",
    nextStep: "Confirm the shareholder loan treatment with Farouk & Co",
    source: "Email from Nadia Farouk, 10 Nov 2026",
  },
];

const emails: ActionEmail[] = [
  {
    id: "e-1",
    ownerId: "jules",
    fromId: "p-karim",
    subject: "Buyer's request list: who answers section 4?",
    receivedAt: "2026-11-06T16:20:00+04:00",
    dealId: "d-pearl",
    message: "Jules,\n\nMeridian sent their due diligence request list. Section 4 asks for all employee contracts and visas. Should our HR manager upload these directly, or should they go through you first?\n\nKarim",
    suggestedAction: "Explain the upload route",
    draftReply: "Hi Karim,\n\nPlease send section 4 to me first. I will check each file and upload it to the data room, so nothing personal goes out by mistake. A zip by email or a Drive link both work.\n\nBest regards,\nJules",
  },
  {
    id: "e-2",
    ownerId: "jules",
    fromId: "p-layla",
    subject: "Falcon: questions on 2025 EBITDA add-backs",
    receivedAt: "2026-11-11T07:52:00+04:00",
    dealId: "d-falcon",
    message: "Hi Jules,\n\nThanks for the CIM. Before our investment committee on Monday we need to understand two add-backs in the 2025 EBITDA bridge: the owner's salary adjustment and the one-off clinic refit. Could you share the support, or set up a short call with the accountant this week?\n\nBest,\nLayla",
    suggestedAction: "Send support and offer a call",
    draftReply: "Hi Layla,\n\nThanks for the quick read. I will send the support for both add-backs by Thursday: a market benchmark for the owner's salary and the refit invoices. If useful, we can also set up a 30-minute call with the company's accountant on Thursday or Friday.\n\nBest regards,\nJules",
  },
  {
    id: "e-3",
    ownerId: "jules",
    fromId: "p-tom",
    subject: "Intro: two logistics owners open to talks",
    receivedAt: "2026-11-11T06:30:00+04:00",
    message: "Jules,\n\nTwo owners of freight forwarders in Dammam told me they would take a call about a sale. Both are around $8M revenue. Happy to introduce if this fits a mandate.\n\nTom",
    suggestedAction: "Accept the intro for Project Atlas",
    draftReply: "Hi Tom,\n\nThank you, this fits a buy-side search we are running. Please introduce us to both owners. I can take calls on Sunday or Monday next week.\n\nBest regards,\nJules",
  },
  {
    id: "e-4",
    ownerId: "jules",
    fromId: "p-priya",
    subject: "Thursday call: can we move to Friday?",
    receivedAt: "2026-11-10T18:20:00+04:00",
    dealId: "d-atlas",
    message: "Hi Jules,\n\nOur CFO is travelling on Thursday. Can we move the target review to Friday morning?\n\nPriya",
    suggestedAction: "Confirm Friday at 10:00",
    draftReply: "Hi Priya,\n\nFriday at 10:00 works. I will send an updated invite with the five target profiles attached.\n\nBest regards,\nJules",
  },
  {
    id: "e-5",
    ownerId: "jules",
    fromId: "p-nadia",
    subject: "Draft 2025 management accounts for review",
    receivedAt: "2026-11-10T16:05:00+04:00",
    dealId: "d-cedar",
    message: "Dear Jules,\n\nAttached are the draft 2025 management accounts for Brewline. Please confirm how you want the shareholder loan treated before we finalise.\n\nKind regards,\nNadia",
    suggestedAction: "Confirm review by Friday",
    draftReply: "Dear Nadia,\n\nThank you. I will review the draft and come back on the shareholder loan by Friday.\n\nKind regards,\nJules",
  },
];

const workstreams: Workstream[] = [
  { id: "w-1", ownerId: "jules", name: "Falcon buyer list, second wave", status: "In progress", nextStep: "Add 10 pet care platforms from Buyers search", dueDate: "2026-11-13", linkedTo: "Project Falcon" },
  { id: "w-2", ownerId: "jules", name: "Cedar data pack", status: "Blocked", nextStep: "Waiting for the 2025 management accounts", dueDate: "2026-11-12", linkedTo: "Project Cedar" },
  { id: "w-3", ownerId: "jules", name: "Engine prototype", status: "In progress", nextStep: "Agree the Home layout with the team", dueDate: "2026-11-14", linkedTo: "Rock: launch the Engine" },
  { id: "w-4", ownerId: "jules", name: "Accounting partner program", status: "Not started", nextStep: "Shortlist 3 accounting firms", dueDate: "2026-11-20", linkedTo: "Rock: 5 referral partners" },
];

const agenda: AgendaItem[] = [
  {
    kind: "meeting",
    id: "m-1",
    ownerId: "jules",
    title: "Falcon: weekly client update",
    start: "2026-11-11T10:00:00+04:00",
    end: "2026-11-11T10:30:00+04:00",
    dealId: "d-falcon",
    attendeeIds: ["p-omar"],
    recent: [
      { date: "2026-11-10", text: "Call: agreed the buyer shortlist" },
      { date: "2026-11-06", text: "Email: sent the CIM draft for review" },
      { date: "2026-11-03", text: "Meeting: site visit at the main clinic" },
    ],
  },
  {
    kind: "meeting",
    id: "m-2",
    ownerId: "jules",
    title: "Weekly team meeting",
    start: "2026-11-11T12:30:00+04:00",
    end: "2026-11-11T13:30:00+04:00",
    attendeeIds: [],
    recent: [],
  },
  {
    kind: "meeting",
    id: "m-3",
    ownerId: "jules",
    title: "Pearl: management presentation",
    start: "2026-11-11T15:00:00+04:00",
    end: "2026-11-11T16:00:00+04:00",
    dealId: "d-pearl",
    attendeeIds: ["p-youssef", "p-karim"],
    recent: [
      { date: "2026-11-10", text: "Email: signed LOI received" },
      { date: "2026-11-05", text: "Call: LOI terms agreed" },
      { date: "2026-10-29", text: "Meeting: first meeting with management" },
    ],
  },
  { kind: "deadline", id: "dl-1", ownerId: "jules", title: "Falcon: first-round offers due", date: "2026-11-12", dealId: "d-falcon" },
  {
    kind: "meeting",
    id: "m-4",
    ownerId: "jules",
    title: "Atlas: target review",
    start: "2026-11-13T10:00:00+04:00",
    end: "2026-11-13T11:00:00+04:00",
    dealId: "d-atlas",
    attendeeIds: ["p-priya"],
    recent: [
      { date: "2026-11-10", text: "Email: asked to move the call to Friday" },
      { date: "2026-11-04", text: "Call: agreed the screening criteria" },
      { date: "2026-10-27", text: "Meeting: buy-side mandate signed" },
    ],
  },
  { kind: "deadline", id: "dl-2", ownerId: "jules", title: "Cedar: teaser to client for approval", date: "2026-11-13", dealId: "d-cedar" },
];

const scorecards: Scorecard[] = [
  {
    ownerId: "jules",
    weekOf: "2026-11-09",
    workdaysElapsed: 2,
    metrics: [
      { id: "s-new-buyer", label: "New buyer conversations", kind: "count", target: 5, taggedIds: ["p-layla", "p-daniel"] },
      { id: "s-buyer-catchup", label: "Buyer catch-ups", kind: "count", target: 4, taggedIds: ["p-sara", "p-youssef", "p-priya"] },
      { id: "s-partner-catchup", label: "Referral partner catch-ups", kind: "count", target: 2, taggedIds: [] },
      { id: "s-linkedin", label: "LinkedIn schedule followed", kind: "yes-no", target: 1, taggedIds: [], done: true },
    ],
    suggestedPersonIds: ["p-priya", "p-layla"],
  },
];

const dataRoom: DataRoomEvent[] = [
  { id: "v-1", dealId: "d-falcon", at: "2026-11-11T07:10:00+04:00", text: "Gulfstone Partners opened the teaser (2 views)" },
  { id: "v-2", dealId: "d-falcon", at: "2026-11-10T21:40:00+04:00", text: "Arcadia Pet Ventures downloaded CIM v3" },
  { id: "v-3", dealId: "d-pearl", at: "2026-11-10T14:05:00+04:00", text: "Meridian Health Holdings opened 12 files" },
  { id: "v-4", dealId: "d-falcon", at: "2026-11-09T11:30:00+04:00", text: "Teaser link sent to Oasis Growth Fund" },
];

const activity: ActivityEvent[] = [
  { id: "a-1", at: "2026-11-11T08:20:00+04:00", actorId: "hugo", text: "moved Project Dune to Mandate signed" },
  { id: "a-2", at: "2026-11-11T08:05:00+04:00", actorId: "maria", text: "added 2 people met to Hugo's scorecard" },
  { id: "a-3", at: "2026-11-10T18:10:00+04:00", actorId: "ramzy", text: "logged NDA signed: Sandcrest Freight on Project Atlas" },
  { id: "a-4", at: "2026-11-10T16:30:00+04:00", actorId: "ramzy", text: "created a new deal: Project Orbit" },
  { id: "a-5", at: "2026-11-10T14:05:00+04:00", actorId: "jules", text: "received the signed LOI on Project Pearl" },
];

const briefs: Brief[] = [
  {
    ownerId: "jules",
    sentAt: "2026-11-11T07:30:00+04:00",
    bullets: [
      "2 tasks are overdue: the Oasis NDA (Falcon) and the Ivorybay leases (Pearl).",
      "Karim Aziz has waited since Friday for an answer on the request list.",
      "Arcadia downloaded the Falcon CIM last night and asked about add-backs this morning.",
      "Meridian signed the Pearl LOI. The move to Due diligence waits for your approval.",
      "3 meetings today, the first at 10:00 with Omar Khalil.",
    ],
  },
];

const toolTabAnswers: Partial<Record<UserId, ToolTabAnswer>> = {};

export const seed = {
  users,
  people,
  deals,
  tasks,
  pendingItems,
  emails,
  workstreams,
  agenda,
  scorecards,
  dataRoom,
  activity,
  briefs,
  toolTabAnswers,
};
