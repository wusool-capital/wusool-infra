# Changelog

Significant changes to the Wusool platform, newest first. This file records
product and operational milestones rather than individual implementation
details. Git history remains the source for commit-level changes.

The project has no version tags: merges to `dev` and `prod` deploy their
 respective environments. See [Delivery status](gitbook/operations/delivery-status.md)
for current production evidence and open handover items.

## 2026-10-06

### Added

- Scribe desktop's menu-bar icon shows a red dot while recording and an
  amber dot while recording is paused.

### Changed

- Scribe desktop opens the meeting as soon as a stopped recording is saved,
  so you can review, edit or summarize the transcript right away. This
  covers the Stop button, the menu-bar item, the pill's "Stop now" and
  auto-stop when a meeting ends. Auto-stop used to open the home page
  instead. Scribe also comes to the front when the meeting opens.
- The "Before we match" popup and `/check-buyer` now list note conflicts
  and missing profile fields under separate headings. Each item names the
  `/edit-buyer` field to fill in.

## 2026-10-05

### Added

- Insights reports can be published behind a lead gate. The business writes
  a report in the new Wusool Reports Studio (Sanity) and publishes it. Its
  `/insights` card is then created automatically in Webflow.
  - Readers see the first quarter of the report, then a short name, email
    and organisation form. The full report opens in place without a reload.
  - Each reader becomes an organisation and a person in Attio, with no role
    and no deal, plus an interaction row. Returning readers skip the form.
  - Ticking "Pin to top of /insights" makes a report the featured card and
    unpins the previous one.
  - Existing hand-written articles stay open.
  - Reports exported as self-unpacking pages, which build themselves with
    JavaScript, are drawn once in headless Chromium on publish and served
    as static HTML. This makes them splittable, and on phones they shrink
    to fit. The toolkit image grows by about 590 MB.

## 2026-10-04

### Added

- Scribe has a changelog page in the GitBook docs listing what changed in
  each version. The menu-bar "View Changelog" item and a "View full
  changelog" link in the update dialog open it in your browser.
- Scribe desktop has an "Open at Login" setting under Recording, on by
  default. Scribe starts in the menu bar when you log in, without opening its
  window, so it is already running for your meetings. Existing users get it
  switched on the first time they run this version, and macOS shows a
  "Background Items Added" notice. Turning the setting off sticks.
- Scribe desktop meetings that belong to a folder have a back button at the
  top that returns to that folder's meeting list. It always goes to the
  meeting's own folder, never to another one you visited earlier.

### Changed

- Sellers found via Google Maps after `/find-match` are saved automatically
  only when Diffbot or People Data Labs matched the same website as Google
  Maps.
- When the websites don't match, nothing is saved. A "Website check" message
  shows both websites and the proposed values. Its **Review & Save** button
  opens the prefilled add-seller form and keeps working after a restart.
- For 30 days, later searches skip a lead that is already waiting for review.
  Websites on Instagram, Facebook, Google Sites, Salla, Zid, Shopify and
  similar platforms count as "no website". A reviewed seller keeps its Google
  Maps place id, so the next search skips it.
- Scribe desktop's "Processing recording" and "Finalizing transcription"
  messages now look the same after you stop a meeting. They also sit in the
  same spot instead of jumping between two styles.
- `/find-match` now always opens a popup after you confirm the buyer, listing
  any missing or conflicting buyer details. The match only starts when you
  click **Run anyway**. Before, missing details were posted as a channel note
  while the match ran, and conflicts paused it behind buttons in the channel.
  If the check itself fails, the popup says so rather than showing an
  all-clear.
- `/find-match` and `/check-buyer` now understand everyday wording in your
  note, such as "pharma tech only, UAE, $5-15M ticket". Each problem gets one
  plain sentence, for example "Heads up: Cursor's profile says vertical is
  Pharma, but you said Garage."
- An amount in your note only counts as a ticket size when you label it as a
  ticket, check size, investment or deal size.
- Open-ended amounts such as "at least $2M ticket" or "EBITDA $1-3M" only
  conflict when they can't overlap the buyer's range.
- A sector that fits several profile options, such as "clinics", only
  conflicts when none of them match. Anything you exclude, such as "no
  pharma", is not checked.
- A region you name is flagged only when it can't overlap the buyer's, for
  example GCC against a Europe-only buyer. Before, region conflicts were never
  raised.
- If your note can't be read, the message lists what's missing and says the
  note couldn't be checked. It never reports that nothing conflicts. An empty
  note is checked instantly.
- A buyer's target regions and target countries now count together. Geography
  is reported missing only when both are empty. A country you name, such as
  "UAE", is flagged only when the buyer's regions and countries don't cover
  it. Before, a buyer with only target countries was never checked.
- The `/find-match` and `/check-buyer` messages now end with how your note
  was read, so a misread is easy to spot. For example: "Read your note as:
  Pharmaceuticals / Biotech · United Arab Emirates".
- EBITDA is reported missing only when both the floor and the ceiling are
  empty.

### Fixed

- `/find-match` matches a buyer's regions and countries together. A GCC buyer
  now matches a seller tagged "UAE" or "KSA". A buyer targeting GCC plus Egypt
  keeps sellers from either. Before, each geography had to match on its own,
  and region names never matched a seller's country.
- A region you name in your `/find-match` note that can't be listed country by
  country, such as Europe, no longer drops almost every seller.
- Google Maps seller search after `/find-match` covers every target region and
  country, not just the first.
- Country names written differently across the CRM, such as Turkey and
  Türkiye or Hong Kong and Hong Kong SAR, now match each other.
- `/check-buyer` shows an error in its popup if the buyer search fails,
  instead of staying on the loading screen.
- Sellers found via Google Maps after `/find-match` are numbered from 1 in
  their own message, instead of continuing on from the CRM shortlist.

## 2026-10-03

### Added

- Scribe desktop has more transcript editing controls before you summarize.
  Select lines with the checkboxes (Shift-click for a range), then delete or
  merge them. Right-click a line to delete everything before it, which clears
  small talk in one step, or to split it. Find & replace fixes a misheard
  name across the whole transcript. Undo and redo (Cmd+Z, Cmd+Shift+Z) cover
  every change. Deleted lines are removed from what Summarize sends. A
  "Proofread" button for AI spelling suggestions shows as "Coming soon".
- New `POST /desktop/transcripts/corrections` endpoint suggests fixes for
  speech-to-text errors (misheard words, company names, punctuation and
  casing) in Scribe desktop transcripts. It never rephrases or removes filler
  words, and nothing is saved on the server.
- Scribe desktop stops recording automatically when a meeting ends. Once the
  meeting app or browser releases the microphone, a pill counts down 15
  seconds, with "Keep" and "Stop now" buttons, then stops. It never
  triggers for recordings where no meeting app was seen. Settings has a
  toggle to turn auto-stop off, in which case nothing appears and recording
  continues until it is stopped manually. Record and Stop now on the
  popups open Scribe's home page, so no extra click is needed.

### Changed

- Scribe desktop now shows the hand cursor on every clickable control,
  including menu and dropdown items. Disabled controls and the read-only
  transcript timestamps keep the normal arrow.
- Scribe desktop's notification popups no longer bring Scribe forward when you
  press the X on "Start recording?" or "Keep" on the meeting-ended countdown.
  They now only close the popup, and your meeting app keeps focus.
- Scribe desktop's start-recording buttons now react the instant they are
  clicked. A spinner shows while the transcription model is checked and
  capture starts. A blocked or failed start puts the button back.
- Scribe desktop's sidebar shows folder names on one line in a smaller size,
  and scrolls long names sideways on hover instead of wrapping. The folder
  page header keeps its meeting and selected counts on one line.

### Fixed

- Scribe desktop folder pages no longer carry selections over from another
  folder, which could delete meetings from the folder you had just left. The
  sidebar also stops highlighting the last opened meeting once you leave it.
- Scribe's meeting popup close button now works on the first click and is
  visible without hovering. The popups no longer show an oversized
  background rectangle behind the card. Both popups now share a refreshed
  card design with the WusoolScribe logo. On macOS they now behave like
  system notifications. Hover and the pointer cursor work, and a click gives
  immediate feedback without pulling focus from the meeting app.

## 2026-10-01

### Fixed

- Back on the first readiness question returns to the welcome screen. It
  previously left a blank page with only the logo.
- A valuation with too little description to identify the business keeps
  the visitor's sector. It no longer shows a confusing "Sector
  reclassified" note or applies the analyst's guessed assumptions.

### Changed

- The valuation tool shows a preliminary valuation after the 10-second
  loading screen, then refines it in place when the analysis lands. A badge
  marks it Preliminary, then Done. Previously results waited for the
  analysis.
- The readiness and valuation tools have a new design: Inter type, a warm
  off-white page and card-style questions. Readiness scores now use shades
  of blue rather than green, amber and red.
- The valuation tool now acts on the analyst's judgement of the business.
  When the auto-assigned sector tag is a poor fit, it uses the analyst's
  growth assumptions, discounts and deal-matching terms. The page flags the
  reclassification.
- The valuation recorded in Attio now uses the same refined inputs. The lead
  is recorded once the analysis finishes, not when the form is submitted.
- Valuation adds a Childcare & Early Education sector. DCF margins now
  mean-revert. The DCF report has an editable illiquidity discount and
  warnings for a dominant terminal value and an implausibly high margin.

## 2026-09-30

### Changed

- A Buyer Network submission now creates one buyer role for each sector the
  buyer ticks, so matching can narrow on each one. Its sectors are no longer
  written to the organisation. A repeat submission updates the roles for
  sectors it already has and adds the new ones. An update replaces the
  role's multi-select answers, such as geography, rather than adding to them.
- Valuation, benchmark and readiness now record the seller's sector on its
  seller role, so matching no longer relies only on the organisation's. A
  resubmission with a new sector replaces the old one.
- `tool_runs.buyer_role_entry_ids` lists every buyer role a submission made.

## 2026-09-29

### Added

- Seller discovery now creates sellers instead of only suggesting them. Each
  search looks at up to 20 Google Maps results. It skips any already in the
  CRM by Google place id or website, and adds the first five new ones.
- Each new seller is filled in with basic company data, then saved to Attio
  and the database. It is posted under the match results with Approve and
  Reject buttons. Approving opens a Qualified deal, as for any other match.
  It also posts the full enrichment proposal, with web research, for review.
- A result that only has a similar name to a company already in the CRM is not
  created. It is posted separately with an "Add as seller" button, so a person
  decides.
- Discovery is capped at 10 searches per buyer per day, so a loop can't fill
  the CRM. The count resets when the service restarts.
- Company lookups now pass the website to Diffbot and People Data Labs, and
  report a rate-limit response instead of treating it as "no data".

- `/add-buyer` and `/edit-buyer` now ask for the vertical in a step of its
  own, before the field form. Pick a vertical the organization already has a
  role for to edit it, or an unused one to create a new role. An
  organization can now hold one buyer role per vertical, so `/add-buyer` no
  longer stops at an organization that already has a buyer role. `/edit-buyer`
  lists each organization once and edits the role's own Attio entry.
- Approving a match now creates a Qualified Buy-side deal in Attio and links
  it to the match. If Attio already has a deal for that buyer and seller, the
  approver is asked whether to promote it or create a new one. If the
  database write fails after Attio succeeds, the approver is told what was
  saved and the sync reconciles the rest.
- A new `/check-buyer <name>` command checks a buyer's stored criteria
  against the advisor's own typed context, on its own or before a match
  run. It flags a stored-criteria conflict (vertical, region, ticket size,
  or EBITDA) and notes anything required that's still missing.
- `/find-match` now runs the same check first. A conflict pauses the match
  behind "Run match anyway"/"Cancel" buttons; missing data alone doesn't —
  it's noted and the match proceeds.
- Organizations can now carry the Places id they were discovered from. A
  company already in the CRM must not be created a second time under a
  slightly different name. Names cannot decide that reliably. The id can.
- The id is unique only where it is set. Most organizations came from a form
  or the old CRM and have none, so a plain uniqueness rule would have allowed
  just one of them.
- Two indexes make the sector and geography narrowing run in the database.
  It previously filtered in Python after fetching every row.

### Changed

- Looking up an organization's active buyer or seller role no longer fails
  when a duplicate is active. It returns the newest. The shared Attio
  role-entry lookup can now be scoped to one buyer vertical.
- `/find-match` now narrows sellers in the database before scoring. It
  filters on the buyer role's vertical, target region and country, and EV
  ceiling. A pharma buyer is no longer scored against industrials sellers.
  Sellers with missing data still pass. The old 1,000-seller cap is gone.
- Sellers valued outside a buyer's cheque size are no longer removed. They
  stay in the pool with a low ticket-fit score. A cheque can buy a partial
  stake in a larger company.
- What the advisor types into the context box now outranks the CRM. Say
  "Egypt" for a buyer stored as US, and the search runs on Egypt. It replaces
  the stored geography or vertical, including in the database narrowing.
  A stated ticket size or EV cap replaces the stored one too. A bare amount
  with no label, such as "up to 10M", sets neither. The result message now
  says so. Explicit limits
  such as a 500K EBITDA floor can also remove sellers.
- "Run match anyway" now keeps the advisor's context. Before, it ran on the
  stored criteria alone. The context box is capped at 900 characters.
- The `client_type` scoring criterion is retired. It never matched anything.
  The CRM holds an engagement type where the scorer expected a customer type.

### Fixed

- A buyer's verticals can no longer be silently collapsed by a routine sync.
  The nightly resync ran against an older deployment on 28 September. It
  reconciled active roles per organization rather than per vertical. That
  switched off 639 of 913 live roles. No data was deleted. Only the active
  flag moved, and it has been restored.
- The same rule still exists in the PowerShell list sync, which was never
  taught about verticals. `sync-lists.ps1` now refuses buyer roles unless
  explicitly forced. The full sync skips them with a warning instead.

### Added

- A repair script restores a buyer's active roles, one per vertical. It
  applies the same rule as the deployed reconciler. Running it twice changes
  nothing, which is how the two are verified to agree.
- Meeting notes now attach to the organization, not to one arbitrary vertical.
  A note carries no signal saying which vertical it concerned. All 178 links
  were cleared. The note's company is unchanged.
- A reviewed script can purge soft-deleted rows from the mirror. It reports
  the approval history that would cascade away before anything is deleted.

### Changed

- The retired `target_geography` and `geographic_focus` attributes are
  archived on buyer roles. Every production buyer had already been converted
  to target region and target country.

## 2026-09-28

### Added

- Scribe desktop can now delete a meeting or a whole tag folder, and always
  removes its recording folder from disk. For a meeting already pushed to
  the server, an opt-in checkbox also soft-deletes the server's `meetings`
  row and deletes its Attio note.


## 2026-09-23

### Added

- Two migration steps now run at the end of a full CRM sync. The first gives a
  buyer one role per vertical, taken from its organization's sectors. A buyer
  hunting five industries becomes five roles. An advisor can then search one
  at a time. The second step fills a seller's own sector from its organization.
- Both steps are re-runnable. A buyer or seller that arrives later lands
  unclassified. The next sync grades it, so no one-off migration is needed.

### Changed

- A buyer's active role is now reconciled per (organization, target vertical),
  not per organization. A buyer hunting several verticals keeps one live role
  in each. Nothing changes visibly until the backfill runs: every role's
  vertical is still empty, which is a single group. Seller roles still
  reconcile per organization.

## 2026-09-18

### Added

- **Get Started** is now a selectable lead-magnet on an organization's
  `lead_source_detail`, alongside the Valuation Tool, M&A Readiness Tool,
  Buyer Form and GCC SME Benchmark. Like the Benchmark before it, the tool
  postdates the legacy workspace, so there is no historical data to backfill
  — it only needs somewhere for new leads to land.

## 2026-09-17

### Added

- The M&A Readiness Tool and Valuation Tool now unlock the full report a
  few seconds after the booking-CTA is clicked. The unlocked report can be
  saved as a PDF via browser print.
- The **Get Started** form now sends the same two SES emails the other four
  lead magnets do. A visitor gets a confirmation with a "Book a Call" link.
  The team gets an internal notice with the submitted figures and links back
  to the Attio organisation/deal. It had been left out of the email dispatch
  when that feature shipped, since Get Started didn't exist on `dev` yet.

### Changed

- The four lead magnets are Valuation Tool, M&A Readiness Tool, GCC SME
  Benchmark, and Buyer Form. None of them reject a repeat submission with
  `409 you have already completed this` any more.
- A visitor can resubmit any number of times, for any tool. Every
  genuinely new attempt gets its own permanent row and its own CRM
  activity entry. Nothing is ever lost or merged.
- Dedup at the organization/person level is unaffected. A repeat
  submission still updates the same Attio organization and person rather
  than creating a new one.
- An exact retried request — a network retry of the same submission, not
  a new visit — still reuses its original row instead of reprocessing.
  A visitor is never emailed twice, and the M&A Readiness Tool is never
  double-billed for its Bedrock call.

## 2026-09-16

### Added

- The four lead magnets (Valuation Tool, M&A Readiness Tool, GCC SME
  Benchmark, Buyer Form) now stamp `organizations.lead_source_detail`
  themselves, on every submission. The field existed since 2026-09-15, but
  nothing wrote it except the historical migration and manual Attio edits.
  If a company submits through more than one tool, the most recent tool
  wins — the same behavior as every other lead-magnet-supplied organization
  attribute.

### Fixed

- Organizations removed from Attio (soft-deleted, `removed_at` set) could
  still surface: a new lead-magnet submission could dedupe-match and reattach
  itself to a removed org's old record instead of creating a fresh one, and
  the matching engine's candidate pool for `/find-match` could still include
  sellers on a removed organization, or seller roles superseded by a newer
  submission (`is_active = false`). Also affected `/edit-seller`'s,
  `/edit-buyer`'s, and `/find-match`'s buyer-resolution org-name search,
  which already excluded superseded roles but not removed orgs. All four
  queries now exclude removed organizations.

## 2026-09-15

### Added

- Organizations now record **which lead-magnet a lead came in through** —
  Valuation Tool, M&A Readiness Tool, Buyer Form, or GCC SME Benchmark — in a
  new `lead_source_detail` field on both Attio and Postgres. The existing
  `lead_source` only ever said Inbound or Outbound, so "which leads came from
  the Valuation Tool?" could not be answered outside the legacy workspace.

  The tool name had never been lost in translation: the migration simply never
  read it, even though the mapping configuration had described carrying it
  across since the beginning. Where a company used two tools, the most recent
  one is recorded, and a genuinely ambiguous pair (identical timestamps) is
  reported rather than guessed at.

- Every lead-magnet submission (Valuation, M&A Readiness, GCC SME Benchmark,
  Buyer Network) now sends two emails via SES: a branded confirmation to the
  visitor with a "Book a Call" link, and an internal notice to the deal team
  with the submitted details and links back to the Attio organisation/deal.
  Both are tracked and retried independently, so a failed send never
  re-sends an email that already landed and never risks the lead itself —
  the Attio write is already durable by the time either email is attempted.
  A CloudWatch alarm now fires on the shared environment alert topic if a
  send permanently fails after SES's own retries are exhausted.

- A record deleted in Attio now disappears from Postgres for **all six**
  mirrored objects, not just two. Deals, notes, buyer roles and seller roles
  had no way to record a deletion at all: a deal deleted from the CRM stayed
  in Postgres indefinitely, so matching, reporting and Slack search kept
  counting and offering records nobody could see in Attio any more. The
  webhook now marks them removed within seconds, and a record re-created in
  Attio comes back live on its own.

  The removal is recoverable by design — rows are marked, never erased,
  because their Postgres-side children (deal-stage history, generated
  documents, match results) are computed here and could not be rebuilt from
  Attio. Deletion stays authored in Attio only; there is still no way to
  delete a record from Slack or from Postgres.

### Fixed

- A person deleted in Attio and then re-created in it came back invisible:
  the deletion marker was never cleared on re-appearance, so the row was
  present but skipped by everything that filters out deleted records.

- Seller discovery's geography restriction silently produced wrong results
  for a buyer whose `target_geography` includes a multi-country region:
  geocoding the bare string `"GCC-wide"` (or the raw `"GCC-wide, Global"`
  buyers actually carry) matched an unrelated US institution commonly
  abbreviated "GCC" with `status: OK` and no error, restricting the search
  to Glendale, CA instead of the Gulf states the buyer meant — traced live
  from a buyer with `target_geography: ["GCC-wide", "Global"]` returning
  only German sellers. Geocode results are now validated against Google's
  own place-type and partial-match signals before they're trusted, and
  `target_geography`'s known multi-country regions (GCC, MENA) and
  explicit no-restriction terms (Global, Worldwide) resolve from a fixed
  table instead of a single geocode call that can't answer them correctly.

## 2026-09-14

### Added

- WusoolScribe desktop app: a "Send feedback" bug icon in the sidebar opens
  a form (category, message, optional contact) that a new
  `POST /desktop/feedback` route on the `meetings` module durably records
  in a new `feedback_submissions` table and best-effort emails via AWS SES
  (`notifications` module) — no email credential ships in the desktop
  binary, and a submission is never lost even if SES delivery fails.
- Every lead-magnet submission now creates an Attio deal at stage
  **Inbound**, so a new lead lands in the pipeline instead of waiting to be
  keyed in by hand. One deal per organisation: a company that runs two tools
  is one lead, and a deal an advisor has already advanced is never dragged
  back to Inbound. Each deal is assigned to an advisor on creation, with a
  configured fallback so the write cannot silently stop if that advisor
  leaves the workspace.
- The site's **Get Started** form is now served by the platform instead of
  Tally, as the fifth lead-magnet tool. A submission records the lead before
  anything else can fail. It then writes the company, the contact, and the
  seller's own figures — revenue, EBITDA, years in business, and sell
  timeline — to the CRM. It embeds as a modal, so the existing button opens
  it in place and the page's URL never changes. The visitor now sees a
  confirmation instead of the form silently vanishing.

### Changed

- Replaced `discovery`'s Firecrawl Google Maps scrape with Google's Places
  API (New) and Geocoding API. Seller leads now carry a real place link
  (`googleMapsUri`) instead of one recovered by regex-matching scraped
  links, and a buyer's geography is enforced against each result's country
  rather than only appearing as words in the search query.

### Fixed

- Buyer requirement extraction now sees a buyer's `target_geography`,
  `ebitda_ceiling`, and several other already-structured `buyer_roles`/
  `organizations` fields that were silently dropped between the database
  row and the Bedrock prompt. A buyer with a real, populated
  `target_geography` (e.g. "GCC-wide, Global") could still trigger a fully
  unrestricted seller-discovery search, because nothing ever told the
  extraction step it existed — traced live from a UK-HQ'd buyer's search
  surfacing Frankfurt/Cologne results with no geography signal anywhere in
  the query. Also fixes a buyer with no free-text investment strategy/notes
  on file: the prompt used to show the literal placeholder `Unknown` for a
  blank field, which the model would sometimes echo back as if it were real
  buyer data (a search for "Unknown companies").
- A visitor who retried a lead-magnet form after a dropped network response
  was told they had already completed it. Each click generated a new
  submission id, so the retry looked like a second visit rather than the same
  one. The id is now fixed for the life of the page, which the Buyer Network
  and M&A Readiness forms could both hit.
- A stale lead-magnet submission stuck in the retry queue could abort the
  entire sweep instead of just itself. That could roll back every other lead
  the same pass had already finished. The write contract promises a failure
  "never" escapes the retry step. That wasn't quite true for the Buyer
  Network's target geography, which has been live since it shipped.

## 2026-09-13

### Added

- A failed nightly Attio resync now raises an alert on the environment alert
  topic instead of being visible only in the Actions tab.
- Added a Vale quality gate for the client GitBook, including terminology,
  readability, structure, and page-length rules.
- Added a contributor-facing documentation style guide.

### Changed

- Reorganized the GitBook around consolidated product guides, technical
  references, and operational handover runbooks.
- Added text-based, end-to-end examples with expected results and recovery
  guidance across every product guide.
- Added compact Mermaid flow diagrams for the Toolkit's matching, editing,
  adding, and enrichment workflows.
- Condensed the changelog into milestone summaries; commit-level detail remains
  available in Git history.

### Fixed

- Restored the nightly Attio-to-PostgreSQL full resync, which had failed every
  night from 2026-09-03 to 2026-09-12. Production PostgreSQL relied on the
  real-time webhook alone for that period and should be reconciled against
  Attio.
- Every embedded lead-magnet tool was cut off partway down the form with no
  way to scroll to the rest, losing any visitor who had not already finished.
  The embedded page measured its height from a value that, inside an iframe,
  can never report less than the iframe already was, so the iframe never grew
  past its placeholder; the loader then set `scrolling="no"`, which turned the
  clipped remainder into unreachable content rather than a scrollbar. Height
  is now measured from the page body, the embed carries no fixed dimensions at
  any screen size, and it clears the fixed height the marketing site puts on
  its embed containers.
- The four tools now use the marketing site's DM Sans rather than Inter and
  JetBrains Mono. The Valuation tool in particular was rendering in the
  browser's default serif with form fields overflowing their card: a stray
  `<style>` tag at the top of its stylesheet made the browser discard the rule
  carrying both its font and its box-sizing reset.
- The Valuation form's paired fields no longer stay side by side on a phone —
  inline styles were overriding the small-screen breakpoint.
- Corrected `/toolkit-status` to report the deployed development or production
  environment instead of falling back to `development` in production.
- Lead-magnet submissions (Valuation, M&A Readiness, GCC SME Benchmark, Buyer
  Network) now create or reuse an Attio person record for the visitor's
  email, so a lead lands attached to a CRM contact instead of only an
  organization. Benchmark submissions also now carry their raw financial
  figures, consent flag, and funding stage through to Attio, and M&A
  Readiness's country now reaches the organization record.
- The GCC SME Benchmark form's optional mobile number field was silently
  dropped before it ever reached the server — its own submit script never
  read the field into the request. Now carried through to the visitor's
  Attio person record.
- The Valuation tool's revenue and profit before tax at the visitor's
  last funding raise were computed client-side and shown back to the
  visitor, but never included in the lead submission. Now reaches
  `tool_runs.payload`.

## 2026-09-12

This release period is summarized in
[September 2026 deliverables](gitbook/deliverables/september-2026.md).

### Added

- Delivered Wusool Toolkit as one Slack application for matching, buyer and
  seller profile management, enrichment, discovery, status, and help.
- Added structured company-data enrichment through Diffbot and People Data
  Labs, with Firecrawl and Bedrock fallback research.
- Added WusoolScribe transcript submission, server-side summarization, Attio
  note creation, status synchronization, and signed desktop updates.
- Added Valuation, M&A Readiness, GCC SME Benchmark, and Buyer Network tools
  to the shared Toolkit backend.
- Added Auto Scaling Group recovery, external reachability monitoring, and
  Slack-routed infrastructure alerts for Toolkit.

### Changed

- Consolidated duplicated background-task, idempotency, organization lookup,
  Bedrock retry, and database utilities across server modules.
- Improved matching requirements, confidence reporting, geography handling,
  and public seller discovery.
- Converted profile country and region fields to controlled multi-selects
  while preserving unsupported stored values safely.
- Improved the Attio full-resync pipeline with batched reads and writes and
  end-of-run consistency validation.

### Fixed

- Corrected Firecrawl response parsing that discarded enrichment and
  lead-tool search results.
- Corrected Google Maps discovery queries and direct place links.
- Prevented unsupported multi-select values from being cleared during an
  unrelated profile edit.
- Fixed Slack formatting, enrichment review, provider-data validation, test
  isolation, and Scribe release and push reliability issues.

## 2026-09-08

### Added

- Introduced the client-facing GitBook with user, technical, handover, and
  WusoolScribe documentation.

## 2026-09-07

### Added

- Migrated the four website lead tools into the AWS-hosted backend with a
  durable submission ledger, idempotency, retry sweeper, and Attio writes.
- Added modular-monolith boundaries and architecture checks across the server.

### Changed

- Replaced legacy mandate terminology and fields with the Deal model.
- Standardized buyer, seller, and deal currency fields on USD.

## 2026-09-05

### Added

- Added the meetings module and moved WusoolScribe summarization into the
  Wusool backend, removing the separate hosted summarization dependency.

## 2026-08-31

### Changed

- Renamed the `people` table to `person` and aligned Attio webhook and nightly
  synchronization mappings with the live SOURCE workspace.

## 2026-08-18

### Added

- Established Alembic migrations as the PostgreSQL schema authority and added
  migration consistency checks to CI and deployment.
- Added signed Attio webhooks, nightly full synchronization, and automatic
  webhook pause and resume around bulk migrations.

## 2026-08-16

### Added

- Added branch-based continuous deployment using GitHub OIDC, immutable image
  digests, ordered OpenTofu applies, migrations, and health checks.
- Established separate development and production AWS environments with their
  own networks, n8n instances, databases, secrets, and deployment state.

### Changed

- Consolidated infrastructure into reusable OpenTofu stacks parameterized by
  environment configuration.

## 2026-08

### Added

- Provisioned AWS Bedrock model access for matching and summarization.
- Added n8n invitation and password-reset email through AWS SES.
- Added the initial WusoolScribe database and networking integration.
