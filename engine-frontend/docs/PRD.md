# Wusool Engine: PRD and Architecture

Nov 6, 2026 · @Contact · Draft v0.1

## Summary

The Wusool Engine is one internal web app where every person at Wusool Capital starts and ends the day. It sits on top of the tools we already pay for (Gmail, Calendar, Attio, Notion, Slack, Apollo, Wusool Scribe, WhatsApp Business) and lets an advisor read, decide and act without opening them.

**One goal:** an advisor runs a full day of deal work without opening another tab, and analyst hours per mandate fall. Gmail keeps only mail that needs no action.

Decisions already taken (6 Nov 2026):

| Topic | Decision |
| --- | --- |
| Scope | The Engine is the internal "Wusool OS" surface of Ramzy's Build Spec. Seller, Buyer and Partner portals stay in that spec. |
| Data | Front-end over existing tools. Attio, Gmail, Calendar, Notion, Sanity and VantageKit stay systems of record; the Engine reads and writes through their APIs. |
| Email | Only mail that needs a reply or has a clear call to action reaches the Engine, on Home. Everything else stays in Gmail. |
| Users | Home and tasks: everyone (3 partners, Maria in ops, incoming analysts). Deal pages: advisors only. |
| AI | Drafts only. A named person approves every outbound action, from the Command Center. |
| Devices | Web app, desktop first, with a phone layout for triage, tasks and approvals (installable, no native app). Urgent alerts and the morning brief arrive as Slack DMs. |
| EOS | Workstreams, Rocks and Issues from Notion. Scorecards copied from Attio and editable. Meeting notes stay in Notion. |
| Design | DESIGN.md from Deal Room governs the whole Engine UI: light theme only, navy accent, no helpers in production. |
| UX rule | Any action in 3 clicks or fewer from where its item is shown. Home is always 1 click away. At most one dialog or drawer over a page. |
| Parked | Ramzy's Buy Side tab; Approvals as a separate tab (folded into Home); full Mandate view spec (later session). |
| Builders | Jules and Ramzy build the product; the tech team does integrations later. |
| Engineering rules | Karpathy coding principles: think before coding, simplicity first, surgical changes, goal-driven execution. |
| Stack | React Router 7 + TypeScript front-end on Cloudflare Workers behind Cloudflare Access (Google sign-in). The Python Toolkit (FastAPI, Frankfurt) stays the only backend; the front-end calls it through a typed client generated from its OpenAPI schema and never touches a database directly. |
| First slice | A clickable prototype of all 13 tabs with a demo account and mock data, built one tab at a time with feedback after each. Then Steps 0 to 2 on live data. |
| Hosting | AWS eu-central-1 (Frankfurt) for data and the Toolkit. One internal Google OAuth app for Gmail, Calendar and Drive. |
| Deal stages | Simplified 10: Lead, Qualified, Engaged, Mandate signed, Preparation, Outreach (was Marketing, renamed 9 Nov 2026 to cover buy-side target approaches), Non-binding offers (was Offers: IOIs and LOIs received before one is signed with exclusivity), Due diligence, Closing, Closed, plus Passed and On hold. Engaged (added 7 Nov 2026): the client said yes and the proposal, NDA and contract are being signed; every document card appears from here. Raoof updates Attio later. |
| Tasks | An Engine-owned tasks table in the Toolkit Postgres. Attio tasks are not used. |
| Code | GitHub organization owned by tech@wusoolcapital.com; repos for the Engine and the website; branches and pull requests; Cloudflare deploys a preview per branch. |
| Later (Raoof) | New Attio fields, Unipile messaging, multiples from Postgres (dummy data until then). |

## Problem from first principles

An M&A advisor at Wusool is paid for four things: finding mandates, finding the right counterparty, moving both sides to a signed deal, and keeping every promise on time. Everything else is overhead.

Those four jobs reduce to one loop, repeated hundreds of times per mandate:

1. **Signal arrives** (email, WhatsApp, meeting, LinkedIn reply, Slack message, Attio change).
2. **Advisor decides** what it means for which deal or person.
3. **Advisor acts** (reply, update the record, create a follow-up, draft a document).
4. **Record stays true** so the next decision is fast.

Today each step of that loop lives in a different tool. The signal is in Gmail or WhatsApp, the context is in Attio, the follow-up is in Notion, the notes are in Scribe, the conversation about it is in Slack, and the contact is in Apollo. The advisor is the integration layer: copying, re-reading and re-logging. That is the tool tax.

What we observed:

- Ramzy's Build Spec estimates 340 analyst hours per sell-side mandate today, much of it re-keying, chasing and rebuilding lists.
- Weekly team meetings already link out to three Attio scorecard views, one Attio pipeline view and four Notion databases. The meeting itself is a tour of tools.
- Attio has two Deal objects (one archived) and archived Buyer and Seller lists. The CRM is accurate only when someone remembers to update it.
- The 3 Nov team meeting names email enrichment and Apollo follow-up as the main thing to improve.

First-principles conclusion: the Engine should not be a fifth place to look. It should collapse steps 1 to 4 into one screen where the signal, its context, the proposed action and the record update arrive together, and the advisor only decides.

## Goals, non-goals and success metrics

The Engine succeeds when an advisor passes the tool-tab test for a full week and analyst hours per mandate fall measurably.

**Goals**

1. One screen to start the day: what came in, what is due, what each deal needs.
2. Every email, meeting and message lands on the right deal and person without manual logging.
3. Every action (reply, follow-up, stage change, task) is taken from the Engine and written back to the tool of record.
4. Workstreams, Rocks, Issues and Scorecards live next to deal work, with scorecards computed from data.
5. Buyer lists, enrichment and outreach run from the deal page.

**Non-goals (v1)**

- Client, buyer or partner logins (Ramzy's portals).
- Replacing Attio, Gmail, Calendar, Notion, Sanity or VantageKit as systems of record.
- A full email client. Mail with no action stays in Gmail.
- AI sending anything on its own.
- Building a data room, valuation tool or listing builder. VantageKit stays the data room.
- Ramzy's Buy Side tab (parked).
- Full mobile parity. The phone view covers triage, tasks and approvals only.
- Personal WhatsApp numbers and LinkedIn automation that breaks LinkedIn's terms.

**Success metrics**

| Metric | How measured | Baseline | Target |
| --- | --- | --- | --- |
| Tool-tab test | Days per week a user does not open Attio, Notion or Slack, and opens Gmail only for mail with no action (self-report at day end, plus Engine session time) | Measure in Step 0 | 5 of 5 days for partners within 8 weeks of launch |
| Analyst hours per mandate | Time logged per activity type in the Engine | 340 sell-side, 170 buy-side (Ramzy's estimates) | Measured figure replaces estimate after first quarter; target 50% cut in year one |
| Auto-logged share | Emails and meetings linked to a deal without manual action | Measure in Step 0 | 90% or more |
| Response time | Deal email or WhatsApp without reply after 24h | Measure in Step 0 | Zero overdue at end of each day |

Guardrail metric: zero wrong-recipient or wrong-deal sends caused by the Engine.

## Users and access

Three roles cover everyone. Each person connects their own Google, Slack and WhatsApp Business accounts; the Engine acts as that person, never as a shared bot.

| Role | People | Sees | Does |
| --- | --- | --- | --- |
| Advisor | Hugo, Jules, Ramzy | Everything, including deal pages and pipeline | All actions; approves AI drafts and outbound sends |
| Analyst | Incoming hires | Home, own inbox, tasks, workstreams; deal pages only for deals they are staffed on | Drafts, research, buyer lists, enrichment; outbound to counterparties needs advisor approval per deal setting |
| Ops | Maria | Home, own inbox, tasks, workstreams, EOS; no deal pages | Admin, invoices, contracts, scheduling |

Access rules:

- Sign-in with Google, restricted to @wusoolcapital.com (and @dopaminecap.com during the domain move).
- Fees never render on any screen that can be screen-shared. The Deal Room rule carries over.
- Each user's inbox is private by default. A thread becomes visible to the team only when it is linked to a deal.
- Every write to an external tool is logged with actor, tool, record, before and after.

## Process review: keep, cut, automate

Each current process was tested with one question: does it move a deal or a promise forward? If yes, keep it and remove the manual steps. If it only exists to feed another tool, cut it.

| Process today | Where | Verdict | In the Engine |
| --- | --- | --- | --- |
| Logging emails, meetings and notes on Attio records | Attio, by hand | Automate | Auto-linked by domain and contact; advisor confirms only ambiguous matches |
| Updating deal stage in Attio | Attio, by hand | Automate (propose) | AI proposes a stage change from evidence (NDA signed email, LOI attachment); one click confirms |
| Morning inbox triage | Gmail | Keep, redesign | Home: action emails, WhatsApp and Slack mentions and due tasks; mail with no action stays in Gmail |
| Workstreams database | Notion | Keep | Workstreams screen; owner, status, next step, due date, linked deal or Rock |
| Rocks and Sub-Rocks | Notion | Keep | Quarterly Rocks with linked workstreams and progress |
| Issues list ("only for validating or potential tasks") | Notion meeting page | Keep, simplify | One Issues queue anyone can add to from any screen; resolved into a task or closed in the weekly meeting |
| Scorecards | 3 Attio list views per partner | Automate | Copy of Attio Scorecards with history; people met added in 2 clicks or suggested from the calendar |
| Weekly meeting tour of tools | Notion page with links | Cut the tour | Meeting view that pulls Scorecards, Rocks, Issues, pipeline headlines; notes stay in Notion for now |
| Meeting rating and "went well, learned, improve" | Notion | Keep as is in Notion | Out of scope v1 |
| Buyer universe in Excel, then Attio import via Slack | Excel, Slack Toolkit | Automate | Built on the deal page; written to Attio through the Toolkit write path |
| Apollo enrichment and email reveal | Apollo UI, Claude connector | Keep, move in | Batch enrichment with credit preview and explicit approval |
| One-by-one outreach emails and follow-up tracking | Gmail, spreadsheets | Automate (draft) | Per-counterparty drafts, follow-up reminders at 4 and 9 working days, reply detection |
| Slack for internal discussion of a deal | Slack | Keep, surface | Deal-linked Slack threads shown on the deal; reply from the Engine |
| Slack Toolkit commands (/find-match, /add-buyer, /enrich) | Slack | Keep, add a UI | Same Toolkit functions behind buttons; Slack commands keep working |
| Scribe push to Attio as a note | Scribe on Mac | Keep | Meeting appears on the deal with summary and extracted action items as draft tasks |
| Document checklist per deal (Engagement, Teaser, etc.) | Deal Room v1 | Keep | Carried over unchanged |
| Two parallel Deal objects and archived lists in Attio | Attio | Cut | Clean up in Step 0; the Engine reads only the current `deal` object |

Three processes are candidates to drop entirely once the Engine is live: hand-written status updates to clients (replaced by a weekly draft from deal activity), the Excel buyer tracker per deal, and manual scorecard entry.

## Product: core objects and surfaces

The Engine has 13 tabs in five groups (Mandates merged into Pipeline on 7 Nov 2026). Every object has one tool of record; the Engine owns only drafts, logs and links between records.

**Objects**

| Object | Tool of record | Notes |
| --- | --- | --- |
| Organization | Attio `organizations` | Clients, buyers, targets, partners |
| Person | Attio `person` | Contacts; email and phone are the matching keys |
| Deal | Attio `deal` (Deals\_V2) | Mandate from lead to close; owner; side (sell, buy) |
| Buyer role, seller role | Attio `buyer_roles`, `seller_roles` lists | Feed the Universes and deal counterparties |
| Counterparty | Attio list entries linked to a deal | Status, next step, owner (no tiers: every buyer is treated as tier 1) |
| Action email | Gmail | Only threads needing a reply or with a clear call to action |
| Meeting | Google Calendar + Scribe note in Attio | Event, attendees, summary, action items |
| Task | Attio tasks | Owner, due date, linked record |
| Workstream, Rock, Issue | Notion databases | EOS objects |
| Scorecard | Attio `scorecards` object | One record per week; per-person targets such as "New Buy Side Conversations (5)" and "Met" fields linking people or companies |
| Data room activity | VantageKit API | Views, downloads and access per deal |
| Partner | Sanity (terms, referral links) + Attio (organization) | Leads referred tracked as deals with the partner as source |
| Deal documents | Google Drive deal folder | Engagement letter, proposal brief, NDA |
| Skill | Engine Settings | Same files as the Claude skills, one source |
| Draft, activity log, bottleneck log | Engine | The only data the Engine owns |
| Multiple, comparable | Wusool multiples and comparables database (location to confirm) | Grows from reviewed web results; each entry has source and reviewer |

**Navigation**

&#91;embedded content: Engine navigation · 14 tabs in 5 groups\]

The left nav keeps Buyers and Sellers small, each with Universe and Search grouped under it. Approvals live inside Home. The phone view shows Home, tasks and approvals only.

## Functional requirements

Each requirement ends with a check that can pass or fail. A feature is done only when its check passes on real data.

**Home (Command Center)**

- H1. Removed from Home (9 Nov 2026): Attio tasks stay in Attio; tasks approved on Home are written there.
- H2. Approvals: AI drafts and proposed record updates, each with Approve and Reject on the row; a click anywhere else on the row opens the side panel to edit. Approvals holds record changes only (stage moves, tasks, next steps). Emails to send (drafts, and follow-ups raised by the reminder rule, which have no draft until Generate email on the row or in the panel) sit in the Emails tab under "To send", below "To reply". Shown in the Actions column (Emails | Approvals | Workstreams). *Check: every outbound send in the audit log has an approver.*
- H3. Action emails: only threads that need a reply or carry a clear call to action. *Check: on a 2-week sample, 90% of shown threads are actionable and under 5% of actionable threads are missed.*
- H4. Workstreams: the user's active Notion workstreams; status and next step editable inline. *Check: edits appear in Notion within 60 s.*
- H5. Data room activity: VantageKit views, downloads and access changes on deals the user leads. *Check: an event shows within 15 min.*
- H6. Active mandates: the user's deals with stage, last activity and next step.
- H7. Today and this week: meetings with prep cards (attendees, deal, last 3 interactions), deadlines.
- H8. Scorecard snapshot: this week against targets; add a person met in 2 clicks.
- H9. Live activity across the firm: stage changes, new deals, NDAs, data room views, scorecard updates.
- H10. Daily brief at 07:30 Dubai and an end-of-day tool-tab question.

* H11. Slack DMs from the Engine for urgent action emails, critical tasks due or overdue, approvals waiting, and the 07:30 brief. Each message has Open in Engine (deep link to the item) and, for tasks, Done or Snooze. Approving a send stays in the Engine. Quiet hours and a daily cap per person. *Check: no more than the cap per day; every link opens the right item.*

**Pipeline**

- P1. Attio Deals\_V2 as kanban by stage and as a list, with New deal: the client is searched among the seller roles (sell-side) or buyer roles (buy-side) already in Attio, or added as a new role, so Attio never gets a duplicate; the deal starts at Lead; filter by side (Sell-side, Buy-side, from Attio `deal_type`), deal owner (default: me) and status (default: Active). The list also shows buyers in play, NDAs signed and offers per deal. Drag to change stage writes to Attio. *Check: Attio matches within 5 s.*
- P2. A card opens a quick-view drawer: key fields editable (stage, owner, value, next step, contacts), the business blurb, contacts with title, email and phone, a "Deal view" link (with a back link to the Pipeline as it was), and Next: the deal's one next action by rule (a due buyer follow-up, then an offer to review, then the first unfinished document in deal order, then the written next step), which opens the Deal view on the side panel where it is done.
- P3. Business blurb: an anonymised description for potential buyers, drafted from Attio, the company website, Scribe notes and deal documents. Editable; the approved version is saved on the deal. *Check: codename check passes; every claim traces to a source.*
- P4. Draft engagement letter: a dialog asks the simple terms (fee, minimum, retainer, exclusivity, term). The Engine then uses the existing skills (sell-side or buy-side proposal and agreement, NDA) to create the contract, a proposal brief PDF and an NDA PDF; saves all three in the deal's Google Drive folder (created if missing); and drafts an email to the business owners from the deal owner's Gmail with the PDFs attached. The user reviews and clicks Send. *Check: files in the Drive folder, email in the owner's Sent with attachments, nothing sent without a click.*
- P5. Fees appear only inside the P4 dialog and the generated documents, never on Pipeline, Deal view or any screen-shared page.

**Deal view (was Mandates)**

The Deal view is the command center for one deal, opened from the Pipeline: an overview panel on a white card, then four tabs.

&#91;embedded content: Deal view layout · overview panel and 4 tabs (illustrative values)\]

*Overview panel* (layout from Ramzy's demo)

- MV1. Deal name, code name, side badge, lead advisor. Edit and Email client buttons at top right: Edit opens the same deal drawer as the Pipeline quick view (stage, status, owner, value, next step, contacts, blurb, engagement letter); Email client opens a draft from the deal owner's Gmail to the founder.
- MV2. Stage tracker: one light blue bar per stage, filled up to the current stage, its name under each bar with the days spent in it in brackets ("Outreach (22)"), computed from the Attio stage history. It closes the overview, right above the tabs, under the figures and advisers.
- MV3. Removed (7 Nov 2026): the next step lives pinned in History and is edited in Edit, so the tabs keep the screen. Send CIM to signed buyers moved to the CIM card.
- MV4. Four figures: Revenue (last FY); Gross profit and margin (last FY); EBITDA and margin (last FY); Asking price with implied multiple (asking price divided by last FY EBITDA, computed in code). Gross profit and asking price become Attio attributes. Empty values read "Not set". No fees.
- MV5. Removed (7 Nov 2026): client advisers are not shown; names found in Gmail or Scribe would be guesses. The overview sticks to the top and collapses to the name, buttons and stage bar once the page scrolls.

*Tab 1: Buyers (sell-side) or Targets (buy-side)*

- MB1. Counterparty table from Deal Room v1 with the merged statuses, last contact, next step and VantageKit activity per row (last view, files opened).
- MB2. Find more: runs Buyers or Sellers Search with the deal's profile prefilled. New names are added unenriched (name, website, rationale): no Apollo call and no AI enrichment at this point.
- MB3. Contacts per counterparty, shown when already in Attio (buyers: any number, each enrichment finds the key contacts; sellers: the owner first); otherwise "No contact yet". Enrichment never runs in bulk. *Check: zero enrichment calls without an explicit click.*
- MB4. A row opens the counterparty drawer: company, rationale, contacts, history; Enrich with Apollo (credit cost shown, then approve) to fill up to two contacts; Outreach with a template.
- MB5. The link in outreach follows the counterparty's status: before NDA signed, a tracked VantageKit teaser link; after NDA signed, a VantageKit data room invitation for that buyer. Choose contact and template, edit, send. Logged to Attio and History. *Check: link type matches status in tests.*

*Tab 2: Materials*

- MM1. Seven cards in the order the deal needs them: Proposal, Client NDA, Engagement contract, Financials, Teaser, CIM, Data room. Every deal at Engaged or later shows them, Not started until someone works on them. Buy-side deals show the first three; targets' NDAs are tracked per target in Tab 1.
- MM2. Each card shows its status (Not started, Drafted, Sent, Signed for agreements; Not started, Drafted, Approved for documents; Not started or Live for the data room), the date or version, "N of M in hand" with a bar, and "N to ask the client" when client items are missing.
- MM3. A card opens one drawer with the checklist of what that document needs, split into "From the client" and "From us", each item In hand or Missing with one plain line on why it is needed. A file added in Drive marks the item in hand.
- MM4. When client items are missing, the drawer shows an editable email from the deal owner listing them with the reasons; Send request is the one click that sends it. Logged to History.
- MM5. Draft in Claude (every card except the data room): once the checklist is complete, Open in Claude opens claude.ai with the prompt filled in: the Wusool skill to use, the code name, side, sector, city, last-year figures and the checklist items in the Drive folder. The code name only, never the client's name, so nothing confidential travels in the link. The advisor attaches the skill and folder in Claude. Copy prompt is the fallback.
- MM6. One status move per card (Mark drafted, Send for signature, Mark signed, Approve, Mark live), always a named person's click. Agreements show main terms; fee terms stay hidden until Show terms. An approved CIM offers Send to signed buyers. The Engagement contract card also has Draft contract, which opens the engagement letter (default terms from the skills, worked fee examples, send to the owner) in the same panel; it moved here from the Pipeline drawer on 9 Nov 2026.

Must-have inputs per deliverable card (Rosenbaum Exhibit 6.5, Marks ch. 7, 12 and 16):

| Card | Must-have inputs |
| --- | --- |
| Teaser | Anonymous business description, sector and city, 3 to 5 investment highlights, revenue and EBITDA for the last 2 to 3 years, transaction sought and reason for sale, code name |
| CIM | Executive summary and investment highlights; history, products and services; customers (concentration, top 10 anonymised) and suppliers; management, org chart, who stays; market and competition; growth opportunities and risks; 3 years of financials plus current year; normalised EBITDA reconciled to net income; a 1 to 2 year forecast |
| Financial reconciliation | P&L and balance sheet for 3 years plus YTD; bank statements and VAT returns to test revenue; owner pay versus market; owner discretionary and one-time costs with evidence; related-party items and market rent; maintenance capex and normal working capital; debt to be repaid at close |

*Tab 3: Offers*

- MO1. Sell-side: offers received from buyers. Buy-side: offers sent to sellers. Fields: counterparty, type (IOI, LOI), date, enterprise value, cash at close %, deferred %, earn-out %, conditions, due diligence weeks, exclusivity asked, status, document link.
- MO2. Select offers to compare side by side. (A risk-adjusted value was removed on 7 Nov 2026: overkill for the deal sizes we run.)
- MO3. Add an offer by hand or from an email attachment (small-model extraction, reviewed before saving).

*Tab 4: History*

- MH1. Next step pinned on top: what, owner, due date, one button.
- MH2. Every event, newest first: emails, WhatsApp, meetings with Scribe summaries, stage changes, buyer status changes, documents sent and viewed, offers, approvals. Filters by type and counterparty.
- MH3. Decision points marked with who decided what and why (a buyer passed, a name excluded, an offer rejected). *Check: every event links to its source.*

**Outreach (Command Center)**

- R1. Every counterparty across the user's deals ("Buyers on my deals") and seller lists ("Owners to approach"), with four tiles that also filter: Due today, Waiting for a reply, Replied (reply rate and how many reached a call or NDA), No contact. The list is grouped by those states, each row with its status in words, last message and one action.
- R2. Row action: Generate (template by type, from the skill), then Send. Logs the touch to Attio and sets follow-ups at 4 and 9 working days (Sat, Sun weekend); a reply pauses them. *Check: 3 clicks from the row to sent.*
- R3. Missing contact: Apollo enrichment with the credit cost shown and an explicit approval. *Check: credits used equal credits approved.*

**Buyers and Sellers**

- U1. Universe: every `buyer_roles` or `seller_roles` entry from Attio, with filters and a read-only record drawer. A "..." menu per row holds the actions: buyers (add to a deal, edit), sellers (ask if open to selling, add to a buy-side deal, new sell-side lead, edit). Sellers filter on revenue and EBITDA (`est_revenue`, `est_ebitda`) and "Open to selling" (`appetite_signal`: Unknown, Interested, Warm intro). The drawer ends with an Emails log (subject and date) and has an Edit button. Buyers universe has Add buyer (same form, name, HQ and website first).
- S0. Describe: a plain sentence ("Family offices in the UAE buying nurseries, $5M to $20M cheques") fills the filters and keywords; the smallest model tier once live, word rules in the prototype. Nothing runs until Search is clicked.
- S1. Search: the user picks filters (sector, geography, buyer type, check size and min. EBITDA in USD, from Attio `buyer_roles`; filters apply on Apply); the Engine runs the Toolkit matching and discovery plus Apollo company search and returns a list with an "in Attio" flag.
- S2. Select rows, then Enrich (Apollo contacts, credit preview), then Add as buyer or seller role. Existing companies are matched by domain and never duplicated. Optional: add to a deal, or to the pipeline (buyers: a new buy-side lead with the company as prospective client; sellers: a new sell-side lead). *Check: no duplicate organizations after a 50-row add.*
- S3. Seller search only: "Ask if open to selling" drafts a short note per owner; the user reviews and edits each, then one "Send N notes" click sends the ticked ones (owners already asked or without a contact are skipped with the reason); follow-ups land in Outreach, replies on Home. New owners from Apollo show revenue and employees; EBITDA is filled later in the Universe.

**Scorecards**

- K1. A copy of the Attio scorecards, one person at a time: each weekly target and actual with On Track, At Risk or Behind. Current metrics: New buyer conversations, Buyer catch-ups, Referral partner catch-ups (counts of people tagged) and LinkedIn schedule followed (yes or no). Each person edits their own list (add, rename, remove, set the target). No charts.
- K2. History: the last 8 weeks, newest first; at or above target in green with a check, below in red.
- K3. Add people or companies met to the "Met" fields from a search box; the count updates and writes to Attio. *Check: Attio record matches after each add.*
- K4. Suggests people met from the week's calendar; the user confirms.

**Partners**

- PA1. List of partners from the website's Sanity \`partner\` documents (name, category, description, offer, referral code or link type, URL, locations, company sizes, active, order), plus the partner organization from Attio. Internal terms (commission, agreement, contact) are not public, so they live in the Engine database, never in Sanity.
- PA2. Editing terms writes to Sanity; the existing Sanity to Webflow sync updates the website. A preview and an explicit Publish click come first, since the change is public. *Check: the site shows the new terms after publish.*
- PA4. Add partner opens the same form empty. Active partners are listed on the website; inactive ones are kept but not shown.
- PA3. Leads referred: deals with the partner as source, stage, last contact, follow-up reminders.

**Engine optimization**

- EO1. Computed views: time in each stage against the median, clients with no reply in 7 days, missed follow-ups, outreach reply rate by template and sector, and conversion per pipeline stage.
- EO2. Anyone logs a bottleneck from any page in 2 clicks (what broke, where, which deal). A bottleneck can be promoted to a Notion Issue.
- EO3. Weekly summary of EO1 and EO2 for the team meeting.

**Multiples**

- MU1. Filters: sector, sub-sector, geography, deal size, date range, deal type (strategic, sponsor) and the multiple (EV/EBITDA, EV/Revenue).
- MU2. Ask box: a plain question ("EV/EBITDA for GCC veterinary clinics under $20M, last 3 years") fills the filters, which the user sees and can change before results run.
- MU3. Database first: a table of matching transactions and comparables with multiple, date, size and source, plus median and range. Any row can be excluded and the median recomputes. *Check: every row carries a source.*
- MU4. Web fallback when the database returns fewer than 5 matches: results in a separate "Unverified" section with a link per number. *Check: web numbers never enter the database median.*
- MU5. Save to database: an advisor reviews a web result and saves it with source and reviewer name.
- MU6. Entry points: Cmd+K, and a link from Deal view prefilled with the deal's sector and size.
- MU7. Only database-verified multiples can go into client documents.

**Settings**

- ST1. Skills: every skill used for contracts, proposals, NDAs, emails, invoices, teasers and CIMs, with version, last edit and where it is used. Editing needs admin rights. The Engine and Claude read the same files.
- ST2. GitBook link, admins only.
- ST4. Reports: insights and reports are written and published in Sanity, which already runs the website. The nav has a Reports link (under Firm) that opens Sanity in a new tab; there is no Reports page in the Engine. Revisit only if reports need Engine data, such as sending a report to a buyer list or tracking downloads per deal.
- ST3. Profile: full name, title, role, email and WhatsApp number; every connected account with its status (Connected, Needs attention with the reason, Not connected), last sync and one Connect, Reconnect or Disconnect button; "Add connector" at the top.

**Everywhere**

- C1. Cmd+K search across people, organizations, deals, tasks and actions. *Check: top result correct for 20 sample queries.*

## UX rules and design

The Engine follows DESIGN.md from Deal Room and three navigation rules, each tested in the end-to-end suite.

**Navigation rules**

1. **Three clicks.** Any action takes 3 clicks or fewer from where its item is shown. Typing in a field does not count; the final Save or Send does. Each e2e test records its click count and fails above 3.
2. **Home in one click** from every screen, through the logo and the first nav item.
3. **One layer.** At most one dialog or drawer over a page. A dialog never opens another dialog; a drawer that needs more room links to the full page.

**Design system (DESIGN.md)**

- Light theme only in v1. No dark mode; colours are tokens, so one can be added later without a redesign.
- Navy `#000523` is the accent for primary buttons, selected states, titles and table headers (about 20:1 contrast on white).
- Light blue supports, never leads: sky `#C6E1EE` and sky-soft `#EAF3F8` for hover, selection backgrounds, focus rings and badges. Never as text or behind white text (about 1.3:1 on white).
- Calm surfaces: grey page, white cards, thin borders, one faint shadow, Inter only, brand table style.
- Status never shown by colour alone. Nothing a client should not see on shareable pages. Sentence case, no em dashes.

**Interaction rules**

- No helpers in production: no tooltips, tours or ? bubbles. Labels, buttons and next-step prompts must be clear on their own.
- Pointer cursor and hover effects only on elements that can be clicked. Static text, cards and labels never react to hover.
- Motion only to show a change of state (a drawer opening, a row saved), 150 to 200 ms, off when the user prefers reduced motion.
- Every element earns its place. An element with no action or decision behind it is removed.

**Usable without M&A experience**

- Every deal shows its next step and the one button that does it ("NDA Circulated: 3 out, 1 signed. Next: send the CIM to signed buyers").
- Each stage has a checklist of what must be done before the deal moves on, and which template to use. Content pending from Jules, with the Deal View spec.
- Plain words on screen; guardrails catch beginner mistakes (codename check, approvals, overdue follow-ups).
- *Check: a new analyst runs a practice mandate from Inbound to LOI without asking anyone.*

**Build notes (handover build only)**

- A Build notes toggle, visible to admins in staging only, shows a ? bubble on each main card: what it is, why it exists, where its data comes from. Production never shows it.
- All note text lives in one file and also feeds the GitBook user guide.

**Additions DESIGN.md needs** (it was written for one page): a left nav with groups, kanban cards, the quick-view drawer at pipeline width, a phone layout for Home, a line chart style for scorecard history, and a live activity feed item.

## M&A process checklist (draft for the Deal View session)

Sell-side deals under $25M rarely have every document, so each item is marked Have, Partial or Missing, and a fallback keeps the process moving. Sources: Rosenbaum ch. 6, Marks ch. 7, Ramzy's readiness list. Stage names follow the proposed simplified list, pending the Attio decision.

| Stage | Done before moving on | Fallback when missing |
| --- | --- | --- |
| Qualified | Why the owner sells, price expectation, who decides, timeline; deal-killer screen (litigation, shareholder disputes, unpaid taxes, government actions) | None: these are questions for the first call |
| Mandate signed | Engagement letter signed (sent by Gmail, the signed copy saved in Drive); client advisers recorded (accountant, accounting tool, lawyer, auditor) | No accountant or lawyer: suggest a partner |
| Preparation | 3 years of financials, current-year accounts, trade licence and MOA, top customers, org chart, cap table; teaser, CIM, model, code name; buyer list approved by the seller | No audit: management accounts reconciled to bank statements and VAT returns (Verified retainer). No forecast: a simple one built with the owner. Customer names sensitive: anonymised top 10 |
| Outreach | NDAs signed, CIM sent, data room live in VantageKit, contact log kept | Small deal: short CIM (10 to 15 pages) or teaser plus a financial pack |
| Non-binding offers | IOIs or LOIs in the structured form; LOI signed with exclusivity | None |
| Due diligence | Data room matched to the buyer's request list; Q&A answered; key contracts, leases, employee agreements, debt schedule, VAT and corporate tax registration, sector licences | Missing contracts: owner declaration, disclosed early to the buyer |
| Closing | Purchase agreement, disclosure schedules, consents, funds flow | None |

Buy-side needs its own checklist; Ramzy's Buy Side tab is parked.

## Architecture

The Engine is a web app plus new modules in the existing Wusool Toolkit backend. It reuses the Postgres mirror of Attio, AWS Secrets Manager, Bedrock and the Attio webhook that already run in production ([platform architecture](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/technical.md)).

&#91;embedded content: Engine architecture · app, API modules, cache, tools of record\]

Reads come from the cache for speed; writes go to the tool of record first, then the mirror follows. This is the Toolkit's existing write path, extended to every tool.

**Design rules**

1. **Tool first, then cache.** The Engine never edits a mirrored field only in Postgres; the nightly resync would overwrite it ([Attio sync](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/attio-sync.md)).
2. **The Engine owns only what no tool holds:** the cross-channel message index (metadata and snippet, body fetched on demand), links between threads and records, drafts, triage state (snoozed, done), tool-tab answers and the audit log.
3. **Act as the user.** Per-user OAuth tokens for Google and Slack, stored in Secrets Manager or encrypted in Postgres. No shared bot sends client email.
4. **One adapter per tool,** each with the same three functions: `pull` (webhook or poll), `push` (write), `link` (resolve to Attio IDs). A broken adapter disables one channel, never the app.
5. **Jobs in Postgres.** Sync, AI and reminder jobs run from a Postgres-backed queue, so state survives restarts.

**Known constraint.** The Toolkit runs on one fixed EC2 instance because report codes, rate limits and duplicate-delivery protection are held in memory ([security](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/security.md)). Mail and calendar sync for five or more users adds steady load. Moving that in-memory state to Postgres is a prerequisite before the Engine's sync jobs go live.

**Frontend.** Open decision. The Deal Room v1 code (React Router 7, TypeScript, 228 tests) can become the Engine front-end and call the Toolkit API, which keeps its Postgres access server-side.

**Current infrastructure** (from the Wusool Deliveries folder):

- The Toolkit is a Python modular monolith (FastAPI, SQLAlchemy, Pydantic, Slack Bolt) on AWS eu-central-1 (Frankfurt), managed with Terraform; Postgres on RDS; Bedrock in the same region.
- n8n (self-hosted) is kept for integration glue only. The delivery team's line: "n8n is integrations and glue. Our code is intelligence, scoring, state and approval."
- Enrichment runs as a waterfall: Diffbot, then People Data Labs, then Firecrawl.
- The Delivery 1 rule applies to the Engine unchanged: modules talk only to the canonical core, through one adapter per tool. Most Engine integrations are plain API calls behind those adapters, with no AI involved.
- Hosting is in Frankfurt; Ramzy's spec assumes the UAE region (me-central-1). See Open questions.

## Integration matrix

Ten of the fourteen sources have APIs for both read and write; web search is read only. WhatsApp and LinkedIn need a decision, and Scribe already flows through Attio.

| Tool | Read into Engine | Write from Engine | Mechanism | Constraint |
| --- | --- | --- | --- | --- |
| Attio | Orgs, people, deals, roles, notes, tasks, scorecards | Same | Existing Toolkit client, webhook, nightly resync | Two Deal objects; Engine uses `deal` only |
| Gmail | All threads, to classify; only action threads shown | Send, reply, draft with attachments | Gmail API per user, push via Pub/Sub watch | Register as an internal Workspace app; mailboxes split across @wusoolcapital.com and @dopaminecap.com |
| Google Calendar | Events, attendees | Create, update, RSVP | Calendar API per user, push notifications | Same OAuth app as Gmail |
| Google Drive | Deal folders and files | Create folders, upload contracts and PDFs | Drive API per user | Folder naming rule per deal to agree |
| Notion | Workstreams, Rocks, Issues | Create and update rows | Notion API, poll every 60 s | Lock synced database properties |
| Slack | Mentions, DMs, deal threads | Post as the user | Events API, user token | Toolkit Slack app already installed; add user scopes |
| Apollo | People, organizations, company search, enrichment | Contact updates | REST API, firm key | Credits; approval per batch, per-user monthly budget |
| Sanity | Partners, terms, referral links | Update partner documents, publish | Sanity API; Toolkit already handles Sanity webhooks and Webflow publishing | Public website: preview and explicit publish |
| VantageKit | Data room views, downloads, access per deal | Access grants (later) | VantageKit API (Jules has access) | Event model and webhooks to confirm from its docs |
| Wusool Scribe | Meeting notes and summaries | None in v1 | Pushes notes to Attio; Engine reads from mirror | Mac only; CRM push not yet verified on a client Mac |
| WhatsApp Business app | Not possible from the app alone | Not possible | The app has no API. Options: Unipile (recommended in the Delivery 1 cost model; also covers LinkedIn and email) or Meta's Cloud API with coexistence (verify terms) | Meta Business account, possibly a provider (BSP), per-conversation fees |
| LinkedIn | Not automated | Not automated | Unipile for authenticated messaging, as the cost model recommends; never scrape | v1: profile links, "log LinkedIn touch" button, Apollo for profile data |
| Web search | Published multiples and transaction data | None | Search API or model web search, provider to choose | Results stay unverified until an advisor saves them |
| DocuSign | Not in v1 (8 Nov 2026) | Not in v1 | Agreements go out by Gmail; the signed copy is saved in the deal's Drive folder | Revisit if signing by email slows deals |

OAuth, tokens and revocation are handled once in the Connectors module, so adding a tool later is a new adapter, not a new app.

## Attio stage migration

Attio's Deal_V2 `deal_stage` field (20 values, read on 9 Nov 2026) mixes three things: where the deal is in the process, events with one buyer (NDA Circulated, NDA Signed), and the outcome (Passed, On Hold, Lost, Failed). The Engine keeps them apart: **Stage** is the 10 steps in order, **Status** is Active, On hold, Passed or Lost, and NDAs live on each buyer's status. The side comes from the existing `deal_type` field (Buy-side, Sell-side), which needs no change.

| Attio `deal_stage` today | Engine stage | Engine status |
| --- | --- | --- |
| Inbound | Lead | Active |
| Qualified, Screened | Qualified | Active |
| Engaged | Engaged | Active |
| Mandate Signed, (Buyer) Mandate Active | Mandate signed | Active |
| Teaser/Data Room In Progress | Preparation | Active |
| Teaser Distributed, NDA Circulated, NDA Signed, CIM Distributed | Outreach | Active |
| LOI Received | Non-binding offers | Active |
| LOI signed/Due Diligence, Exclusivity | Due diligence | Active |
| Offer Signed/ Legal Docs | Closing | Active |
| Closed | Closed | Active |
| On Hold | unchanged | On hold |
| Passed | unchanged | Passed |
| Lost, Failed | unchanged | Lost |

**Steps (Raoof)**

1. Add a `deal_status` select to Deal_V2: Active, On hold, Passed, Lost.
2. In `deal_stage`, rename Inbound to Lead, Teaser/Data Room In Progress to Preparation, LOI Received to Non-binding offers, LOI signed/Due Diligence to Due diligence, Offer Signed/ Legal Docs to Closing, and add Outreach.
3. A one-off script in the Toolkit moves every record by the table above. It runs first in report mode (count per row, nothing written); Jules checks the counts; then it writes. For Passed, On Hold, Lost and Failed it sets the status and puts the stage back to the last process stage in the record's stage history (Lead when there is none).
4. Archive the values left empty: Screened, (Buyer) Mandate Active, Teaser Distributed, NDA Circulated, NDA Signed, CIM Distributed, Exclusivity, Passed, On Hold, Lost, Failed.
5. Leave untouched: `deal_type`, `stage_changed_at`, the archived `deals` object, and Attio's stage history, which the Deal view reads for days per stage.

*Check: every Deal_V2 record has one of the 10 stages and one of the 4 statuses; the counts per stage match the report; the nightly resync leaves them unchanged.*

## Connector build plan

How the prototype becomes live, one connector and one screen at a time. It follows the Build plan steps below and the design rules above; nothing here adds a feature.

**Rules for simple code**

1. **Screens do not change.** Every screen reads and writes through the functions in `app/demo/api.ts`. Going live replaces a function's body with a call to the Toolkit's typed client, keeping its name, inputs and return shape. A tab is live when all its functions are swapped.
2. **One switch.** `app/api.ts` re-exports either the demo module or the live module, chosen by one build setting (`VITE_DATA=demo` or `live`). The demo account in staging keeps working, and the demo data doubles as test fixtures.
3. **One Toolkit endpoint per page read, one per action.** The Toolkit gathers Attio, Gmail, VantageKit and the rest on the server; the browser never calls a tool directly.
4. **Writes go to the tool first** (design rule 1), and every send or record change carries the id of the person who clicked. The Toolkit refuses a write without it, so AI never sends.
5. **One adapter per tool**, with only `pull`, `push` and `link` (design rule 4). No shared framework beyond that.
6. **A broken connector blanks one block, not the page.** The endpoint returns what it has plus `unavailable: ["gmail"]`; the block reads "Gmail is not connected. Reconnect on Profile."
7. **No caching, retries or extra queues until a check fails.** Add them where a measured check says so, not before.
8. **Each endpoint gets a contract test** against the demo fixture's shape, and each connector a "done when" check below.

**Built once (Build plan Step 1)**

- Connectors module: per-user OAuth, tokens in Secrets Manager, revoke, and the status the Profile page shows (Connected, Needs attention with the reason, Not connected, last sync). Connect and Reconnect open the tool's own sign-in.
- Write path for Attio (tool first, then the Postgres mirror), the job queue, the audit log, and the approval check from rule 4.
- Apollo credit gate: the cost shown before the click, a monthly budget per user, refusal above it.

**Connectors, in build order**

| # | Connector | Setup (who, access) | Screens that use it | Limits | Done when |
| --- | --- | --- | --- | --- | --- |
| 1 | Attio | Existing Toolkit client and webhook; no new access | Every tab | Two deal objects: the Engine uses `deal` only | A stage change in the Engine shows in Attio within 5 s and survives the nightly resync |
| 2 | Google: Gmail, Calendar, Drive | One internal Workspace OAuth app (admin: tech@wusoolcapital.com), per-user consent; Gmail read, modify and send, Calendar events, Drive files in deal folders | Home, Deal view (email client, request documents, Materials), Outreach, Scorecards (suggestions), Pipeline (engagement letter) | Gmail push needs a Pub/Sub watch renewed weekly | Jules connects on Profile; Home shows today's agenda and action emails; a reply sent from the Engine is in Gmail Sent; a file dropped in a deal folder marks its Materials item in hand within 1 minute |
| 3 | Notion | Internal integration token; the Workstreams, Rocks and Issues databases shared with it | Home (workstreams), Engine optimization (Make Notion issue) | Poll every 60 s; lock synced properties | A workstream edit in the Engine shows in Notion; Delete moves it to Notion's trash |
| 4 | VantageKit | API key (Jules has access) | Home feed, Deal view (data room column, Data room card), outreach links | Event model and webhooks to confirm | A teaser view appears on the deal page and the Home feed within 5 minutes; outreach sends the teaser link before NDA and the data room invitation after |
| 5 | Wusool Scribe | None: reads its notes from Attio | Deal view History, Home | Mac only | A meeting note appears in the deal's History |
| 6 | Skills repo (GitHub) | Fine-grained token on the skills repository, read and write | Skills, Materials (skill names in prompts), engagement letter | Admin-only edits | Saving a skill in the Engine creates a commit with the change note; Claude reads the same file |
| 7 | Apollo | Firm API key in Secrets Manager | Deal view (enrich), Outreach (Find contact), Buyers and Sellers search | Credits; behind the credit gate | Credits used equal credits approved across one outreach wave |
| 8 | Web search | Provider to choose | Multiples (fallback under 5 matches) | Paid per query | Every web result carries a source link and stays unverified until an advisor saves it |
| 9 | Slack | Existing Toolkit Slack app plus user scopes | Morning brief, urgent alerts | User token per person | The brief posts at 07:30 and a mention reaches the right person |
| 10 | Sanity | Existing Toolkit handler plus a write token | Referral partners | Public website: Publish click only | A partner edit published from the Engine is live on the website after the Webflow sync |
| 11 | WhatsApp, LinkedIn | Not built until the provider decision | Profile shows them Not connected | Unipile or Meta, per-conversation fees | Decided first; then a WhatsApp message on a deal is logged to its History |

Open in Claude needs no connector: it is a link with the prompt in it, and the prompt carries the code name only. No DocuSign in v1: agreements are sent from Gmail and turn Signed when the signed copy is saved in the deal's Drive folder (or by Mark signed).

**Swap map: demo function to Toolkit endpoint**

| Screen | Demo function | Toolkit endpoint | Tools behind it |
| --- | --- | --- | --- |
| Shell | `getCurrentUser`, `getDealNames` | `GET /engine/me`, `GET /engine/deals?fields=name` | Google sign-in, Attio |
| Home | `getHome` | `GET /engine/home` | Gmail, Calendar, Attio, Notion, VantageKit, Engine store |
| Home | `setTaskDone` | `PATCH /engine/tasks/{id}` | Attio |
| Home | `approvePendingItem`, `rejectPendingItem` | `POST /engine/review/{id}/approve`, `/reject` | The item's tool (Gmail, Attio or Notion); Engine store |
| Home | `sendReply`, `markNotActionable` | `POST /engine/emails/{id}/reply`, `/not-actionable` | Gmail; Engine store (teaches the classifier) |
| Home | `updateWorkstream`, `deleteWorkstream` | `PATCH`, `DELETE /engine/workstreams/{id}` | Notion |
| Home | `saveToolTabAnswer` | `POST /engine/tool-tab` | Engine store |
| Pipeline | `getPipeline` | `GET /engine/pipeline` | Attio deals and roles |
| Pipeline | `createDeal`, `createBuySideLead`, `createSellSideLead`, `createSellSideLeadFromSearch`, `createReferredLead` | `POST /engine/deals` | Attio: find the role by name or domain, add it if new, create the deal |
| Pipeline | `updateDeal`, `approveBlurb`, `setNextStep` | `PATCH /engine/deals/{id}` | Attio |
| Pipeline | `sendEngagementLetter` | `POST /engine/deals/{id}/engagement-letter` | Skills repo, Drive, Gmail |
| Deal view | `getDealView` | `GET /engine/deals/{id}` | Attio, VantageKit, Drive, Engine store |
| Deal view | `updateCounterparty`, `addSuggestions` | `PATCH /engine/counterparties/{id}`, `POST /engine/deals/{id}/counterparties` | Attio list entries; Toolkit matching |
| Deal view, Outreach | `enrichCounterparty` | `POST /engine/counterparties/{id}/enrich` | Apollo, behind the credit gate |
| Deal view, Outreach | `sendOutreach` | `POST /engine/counterparties/{id}/outreach` | Gmail, VantageKit link, Attio log |
| Deal view | `sendCim` | `POST /engine/deals/{id}/send-cim` | Gmail, VantageKit invitations |
| Deal view | `requestClientDocuments`, `emailClient` | `POST /engine/deals/{id}/emails` | Gmail |
| Deal view | `setMaterialStatus` | `PATCH /engine/materials/{id}` | Engine store; Drive watch marks items in hand and a signed agreement saved in Drive marks it Signed |
| Deal view | `addOffer`, `setOfferStatus` | `POST /engine/deals/{id}/offers`, `PATCH /engine/offers/{id}` | See open decisions |
| Deal view | `logDecision` | `POST /engine/deals/{id}/decisions` | Attio note |
| Outreach | `getOutreach` | `GET /engine/outreach` | Attio, Gmail (reply detection) |
| Buyers universe | `getBuyersUniverse`, `addBuyer`, `updateBuyer`, `addBuyerToDeal` | `GET`, `POST /engine/buyers`, `PATCH /engine/buyers/{id}`, `POST /engine/deals/{id}/counterparties` | Attio buyer roles (no duplicate domains) |
| Buyers search | `searchBuyers`, `enrichCandidates`, `addCandidatesAsBuyers`, `addCandidatesToDeal` | `GET /engine/buyers/search`, `POST /engine/candidates/enrich`, `POST /engine/buyers`, `POST /engine/deals/{id}/counterparties` | Toolkit matching, Apollo, Attio |
| Sellers universe | `getSellersUniverse`, `updateSeller`, `addSellerToDeal` | `GET /engine/sellers`, `PATCH /engine/sellers/{id}`, `POST /engine/deals/{id}/counterparties` | Attio seller roles |
| Sellers search | `searchSellers`, `enrichSellerCandidates`, `addCandidatesAsSellers`, `addSellerCandidatesToDeal` | `GET /engine/sellers/search`, `POST /engine/candidates/enrich`, `POST /engine/sellers`, `POST /engine/deals/{id}/counterparties` | Toolkit discovery, Apollo, Attio |
| Sellers | `sendOwnerApproach`, `sendOwnerApproaches` | `POST /engine/sellers/approach` | Gmail, Attio list entry |
| Scorecards | `getScorecards` | `GET /engine/scorecards?person=` | Attio scorecards, Calendar (suggestions) |
| Scorecards | `tagScorecard`, `untagScorecard`, `setScorecardDone` | `POST`, `DELETE /engine/scorecards/{person}/metrics/{metric}/tags`, `PUT .../done` | Attio "Met" fields |
| Scorecards | `setScorecardMetrics` | `PUT /engine/scorecards/{person}/metrics` | See open decisions |
| Referral partners | `getPartners`, `publishPartner` | `GET /engine/partners`, `PUT /engine/partners/{id}` | Sanity (public fields), Engine store (terms), Attio (leads) |
| Engine optimization | `getOptimization`, `logBottleneck`, `promoteBottleneck` | `GET /engine/optimization`, `POST /engine/bottlenecks`, `POST /engine/bottlenecks/{id}/notion` | Attio, Gmail, Engine store, Notion |
| Multiples | `getMultiples`, `saveComparable` | `GET`, `POST /engine/multiples` | Postgres comparables, web search |
| Skills | `getSkills`, `saveSkillVersion` | `GET /engine/skills`, `POST /engine/skills/{id}/versions` | Skills repo |
| Profile | `getProfile`, `updateProfile` | `GET`, `PATCH /engine/me` | Engine store, Connectors module |
| Profile | `connect`, `disconnect` | `GET /engine/connectors/{tool}/authorize`, `DELETE /engine/connectors/{tool}` | The tool's own sign-in; token revoke |

**Open decisions per connector**

| Topic | Question | Needed by |
| --- | --- | --- |
| Google | One OAuth app across both mail domains, or move every mailbox to @wusoolcapital.com first | Step 2 |
| Drive | Folder naming rule per deal, and which folder counts as "in hand" for each Materials item | Step 4 |
| Materials, offers | Kept in the Engine store or as Attio objects (Attio keeps them visible outside the Engine) | Step 5 |
| VantageKit | Webhooks or polling, from its API docs | Step 2 |
| Scorecards | Where each person's list of metrics lives: Attio attributes or the Engine store | Step 6 |
| Web search | Provider and monthly budget | Step 6 |
| WhatsApp, LinkedIn | Unipile or Meta Cloud API; cost per conversation | Step 8 |

## AI features and guardrails

AI reads, sorts and drafts; a named person decides. Every AI output lands in Approvals or as a suggestion, never as a sent message or a silent record change.

| Job | Input | Output | Trigger | Human step |
| --- | --- | --- | --- | --- |
| Action-email filter | New Gmail thread + linked records | Shown on Home or left in Gmail; deal link; suggested action | On arrival | Accept, or mark "not actionable" (trains the filter) |
| Reply draft | Thread + deal context + house style | Draft reply | On open, or button | Edit, send |
| Record update | Message or meeting | Proposed stage, status, next step, task | On arrival | Approve on Home |
| Meeting follow-up | Scribe note | Action items as draft tasks, follow-up email, suggested scorecard "met" entries | Note lands in Attio | Approve per item |
| Business blurb | Attio, website, Scribe notes, deal documents | Anonymised blurb for buyers | Pipeline card | Edit, approve |
| Engagement pack | Terms dialog + deal data + skills | Contract, proposal brief, NDA, cover email | Draft engagement letter button | Review, send |
| Daily brief | Overnight activity per user | 4 to 6 bullets with links | 07:30 Dubai | None, internal |
| Outreach drafts | Counterparty rationale, template by type | Draft per contact with "why you" line | Outreach row or Seller search | Read every line, send |
| Optimization summary | Stage times, reply rates, logged bottlenecks | Weekly findings | Before the weekly meeting | Discuss in meeting |
| Multiples search | Question or filters + multiples database | Filters from the question; web results with sources when the database is thin | Ask box or filter change | Review, save to database |

Guardrails:

- **No AI numbers to clients.** Valuations, match scores and fees are rules in code (carried over from Ramzy's spec).
- **Codename check** on every outbound draft: the client's real name blocks the send on sell-side outreach.
- **Provenance.** Each AI call stores prompt version, model, input record IDs and approver.
- **Data stays in AWS.** AI runs through Bedrock, as the Toolkit does today. Transcripts and email bodies never appear in logs.
- **Same skills everywhere.** Existing Wusool skills (NDA, proposals, market research, buyer outreach) become the system prompts, so the Engine and Claude behave the same.

## AI usage policy

Code and APIs do the work by default. An LLM is used only where language must be read or written, and always the smallest model that passes the job's test.

| Task | Method | Model tier |
| --- | --- | --- |
| Syncing tools, linking by email domain, dedupe, stage moves, follow-up dates, scorecard counts, multiples median, match scoring, fees | Code and APIs | None |
| Action-email filter | Rules first (sender known in Attio, thread on a deal, direct question); LLM only for what rules cannot decide | Small |
| Extraction: meeting action items, fields from files, plain-language commands | Structured output checked against a schema | Small |
| Daily brief, weekly optimization summary | Summary of logged events | Small |
| Reply drafts, outreach "why you" lines, business blurb | Draft with house style and skills | Mid |
| Engagement pack, teaser and CIM sections | Locked templates; AI fills only the variable parts | Mid; large only if the test shows the need |
| Multiples and buyer web search | Search tool plus extraction; results marked unverified | Mid |
| Valuations, numbers shown to clients, sending anything | Never AI | None |

Rules (also written into `CLAUDE.md`):

- Tiers map to Bedrock model IDs in one config file; changing a model is a config change, not a code change. Bedrock already offers Claude, OpenAI, Qwen and Kimi under credits; a non-Claude model is used only if it matches quality on the test set at lower cost.
- Every AI job has a small test set and passes it before release and after every model change.
- Every call logs job, model, tokens, cost and latency. Monthly cost per job shows in Engine optimization.
- Prompt caching on house style and skills; non-urgent jobs run in overnight batches.
- A new AI job needs a one-line reason why rules or an API cannot do it.

## Relationship to existing work

The Engine reuses three things already built and conflicts with one decision in Ramzy's Build Spec that the partners need to settle.

| Existing work | What the Engine takes | What changes |
| --- | --- | --- |
| Deal Room v1 (Oct 2026) | Deal page, stepper, funnel, counterparty table, side panel, document checklist, tests, "no fees on screen" rule | Seeded data and Excel import give way to live Attio list entries; becomes the Deal workspace |
| Wusool Toolkit (production) | Attio client, Postgres mirror, Bedrock access, matching, enrichment, discovery, Slack commands, AWS setup | New modules: connectors, linker, approvals, AI jobs; in-memory state moves to Postgres |
| Ramzy's Build Spec (5 Nov 2026) | Wusool OS screens (Today, Pipeline, Mandate workspace, Buyers), outreach engine design, AI guardrails, analyst-hours baseline | Portals stay in that spec; see conflict below |
| Raoof's Month 4 delivery (16 Oct to 12 Nov 2026) | Sellers-to-buyers flow, outreach drafts with follow-up reminders, plain-language Toolkit, cost review; all in Slack today | The Engine becomes the web view Raoof deferred ("if approving long lists in Slack proves clumsy, we will propose a simple web view"). Buyers Search, Outreach and Pipeline call the same Toolkit endpoints, so nothing is built twice. |

**Conflict to resolve.** The Build Spec replaces Attio with a new Postgres system of record and a Next.js app on AWS. This PRD keeps Attio as the record and builds on the Toolkit. Both can be true in sequence: the Engine's adapter pattern means Attio can later be swapped for an Engine-owned database without rebuilding the screens. Recommendation: ship the Engine on Attio first, and decide on replacing Attio only when the client portals need data Attio cannot hold.

## Build plan

Ten steps, each with a check that must pass before the next starts. No dates yet: they depend on the stack decision and on Jules and Ramzy's available hours.

**Engineering rules (Karpathy)**

1. **Think before coding.** Each step opens with a one-page note in the repo: assumptions, what is unclear, the chosen interpretation. Unclear points go to the partners before code.
2. **Simplicity first.** Build only what the step's check needs. No abstraction before its second use; the adapter interface is the one exception, since nine tools share it.
3. **Surgical changes.** Touch only the code the step needs. Toolkit changes stay inside new modules; its architecture tests stay green. Deal Room code is ported, not rewritten.
4. **Goal-driven execution.** Write the step's check first (test, script or measured number), then build until it passes.

**Code and handover standards** (readable by an engineer and by another LLM)

- `CLAUDE.md` at the repo root from day one: the Karpathy rules, the non-negotiables (tool first, AI never sends, no fees on shareable screens, 3-click and one-layer rules, AI usage policy and model tiers), DESIGN.md wins over any design skill, commands, module boundaries, progress log.
- Comments explain why, never what; names carry the what.
- A short README per module and per tool adapter; docstrings on every public function.
- A one-page decision record for each major choice (stack, Attio as record, Slack for alerts).
- Tests written as readable examples of behaviour.
- Handover doc and GitBook updated at the end of every step.
- Front-end skills (/front-end, /taste) may guide craft; DESIGN.md decides colours, type and components.

**Steps**

1. **Step 0: Baseline and cleanup.**
   - Build: one week of tool-time self-reports; archive the legacy Attio Deal object and lists; assign owners for the Toolkit's open high-priority items; collect VantageKit API docs and the Sanity partner schema.
   - Verify: baseline numbers recorded; Postgres restore test passes; Attio has one deal object.
2. **Step 1: Foundation.**
   - Build: move Toolkit in-memory state to Postgres; job queue; Engine schema; Google sign-in; audit log; adapter interface; left nav shell; DESIGN.md additions; click-count test harness.
   - Verify: Toolkit runs on two instances with no duplicate deliveries; all existing tests pass.
3. **Step 2: Home, read only (recommended first slice).**
   - Build: Gmail, Calendar, Attio, Notion and VantageKit adapters (read); action-email classifier; linker; every Home block.
   - Verify: 90% of shown emails are actionable on a 2-week sample; every partner opens Home first for 10 working days.
4. **Step 3: Act from Home.**
   - Build: reply and send, tasks to Attio, inline workstream edits, approve drafts, add people met to scorecards.
   - Verify: one partner goes 5 working days without opening Attio or Notion, and opens Gmail only for mail with no action.
5. **Step 4: Pipeline.**
   - Build: kanban and list on Deals\_V2, owner filter, quick-view drawer, business blurb, engagement letter flow with Drive and skills.
   - Verify: one engagement letter goes from the Engine to a business owner, with contract, proposal brief and NDA saved in the deal's Drive folder.
6. **Step 5: Mandates (Deal view).**
   - Build: overview panel, Buyers, Materials, Offers and History tabs on live Attio, VantageKit and Drive, as specified under Mandates.
   - Verify: one sell-side and one buy-side mandate run for 2 weeks with nobody opening the Attio UI.
7. **Step 6: Scorecards, Multiples, Buyers and Sellers.**
   - Build: Scorecards tab with history; Multiples tab with database search and web fallback; Universes; Search with enrichment and add-as-role.
   - Verify: scorecards match Attio; every Multiples result carries a source; no duplicate organizations after a 50-row add.
8. **Step 7: Outreach Command Center.**
   - Build: cross-deal counterparty table, generate and send, follow-up reminders, reply detection, Apollo enrichment.
   - Verify: one full outreach wave runs from the Engine; Apollo credits used equal credits approved.
9. **Step 8: Partners, Engine optimization, Settings, Slack and WhatsApp.**
   - Build: Sanity partner editing with publish, referral tracking, bottleneck views and log, Skills repo, GitBook link, Slack and WhatsApp adapters.
   - Verify: a partner term change goes live on the site; the weekly meeting uses the optimization summary.
10. **Step 9: Tool-tab test for everyone.**
    - Build: close the gaps users report in the end-of-day question.
    - Verify: all partners pass 5 of 5 days for 4 straight weeks; first measured analyst-hours-per-mandate figure published.

**Why Home first.** Everyone starts the day there, a read-only slice cannot damage any record, and the action-email classifier and linker it needs are the base for every later tab.

## Risks

The largest risk is building a fifth tool that people check in addition to the other four.

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Half adoption | Engine becomes one more tab | Step gates are usage checks, not feature lists; end-of-day prompt names the tool people still open |
| Wrong link or wrong recipient | A client or buyer sees another deal's data | Linker asks when unsure; codename check; approval on every send; audit log |
| Single Toolkit instance | Sync load or a crash stops Slack bot, lead tools and Engine together | Step 1 moves state to Postgres and runs two instances |
| No owners for production infra | Failures go unnoticed | Step 0 assigns owners; alarms on sync failures |
| Builder time | Jules and Ramzy also run deals | One slice at a time; each step usable on its own |
| API limits and costs | Gmail quotas, Apollo credits, WhatsApp fees | Push notifications over polling; per-user Apollo budget; WhatsApp only after a cost check |
| Tool schema drift | A renamed Notion or Attio field breaks sync | Lock properties of synced databases; adapter tests against live schemas nightly |
| Personal data and DFSA record-keeping | Compliance exposure | Data stays in AWS; immutable audit log; review with counsel before Step 6 |

## Open questions

- [ ] Stack: Deal Room code (React Router) as the front-end on the Toolkit API, or Ramzy's Next.js? Pending the extra build context.
- [ ] First slice: confirm Home, read only.
- [ ] Attio long term: keep as record, or replace when client portals launch? This PRD assumes keep.
- [ ] Tasks: Attio tasks as the single task list, with Notion keeping only Workstreams, Rocks and Issues?
- [ ] VantageKit: share the API docs (events, webhooks, deal mapping).
- [ ] Sanity: confirm where partner terms and referral links sit in the schema, and who may publish.
- [ ] Engagement letter dialog: confirm the term fields and the default skill per deal side.
- [ ] Drive: folder structure and naming per deal.
- [ ] Scorecards: keep the per-person fields on one weekly record as in Attio, or move to one record per person per week?
- [ ] WhatsApp: move the firm's WhatsApp Business number to the Cloud API (coexistence), or log WhatsApp by hand in v1?
- [ ] Email domains: are all mailboxes moving to @wusoolcapital.com? Affects the Google OAuth app setup.
- [ ] Analyst access: per-deal staffing, or all deals visible to all analysts?
- [ ] Who owns the Toolkit in production (primary and backup)?
- [ ] Mandates (Deal view): schedule the dedicated spec session.

* [ ] Multiples: where does the multiples and comparables database live today, and what fields does it hold?

- [ ] Raoof: agree the split so the Engine is the web view for Month 4 features, calling the same Toolkit endpoints.
- [ ] Hosting region: stay in Frankfurt (eu-central-1) or move to the UAE (me-central-1) as Ramzy's spec assumes?
- [ ] Messaging: Unipile for WhatsApp and LinkedIn, or Meta's Cloud API for WhatsApp only?
- [ ] Client advisers: add accountant, accounting tool, lawyer and auditor as Attio attributes on the deal or the company?
- [ ] Stages: adopt the simplified deal stages and merged buyer statuses in Attio? Mapping and steps in "Attio stage migration".

* [ ] Deal view: add gross profit, asking price and last FY as Attio deal attributes; confirm the input checklist for Teaser, CIM and Financial reconciliation.

## Sources

- Wusool Platform Build Spec, Ramzy Osman, 5 Nov 2026 (Individual Deal Dashboard folder)
- Deal Room PRD and Handover, 20 and 21 Oct 2026 (Individual Deal Dashboard folder)
- [Wusool docs: platform architecture](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/technical.md), [Attio sync](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/attio-sync.md), [Toolkit](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/toolkit.md), [security](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/technical-documentation/security.md), [delivery status](https://wusool-capital.gitbook.io/docs/vttVgqrltuEtLAJkX7dL/operations-and-handover/delivery-status.md)
- Notion: [Workstreams](https://app.notion.com/p/3bb386f7aa05811482f0eed68b46cd47), [261103 Team meeting](https://app.notion.com/p/409386f7aa05811eaccbf136f4395d32)
- Attio workspace objects and lists, read 6 Nov 2026
