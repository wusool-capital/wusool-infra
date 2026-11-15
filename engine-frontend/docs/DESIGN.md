# Wusool Capital dashboard design

The look of Wusool Deal Room, written so other Wusool dashboards can match it. Source: `app/styles.css` in this repo and the Wusool Capital Brand Guidelines (colors, Inter, the "Illustrative Exit Summary" table).

In one line: a light grey page, white cards with thin borders, Inter only, navy as the single accent, tables in the brand table style.

## 1. Principles

- Quiet and minimalist (shadcn-like), built with plain CSS. No UI framework needed.
- Navy is the only accent. Use it for primary buttons, selected states and table headers, nothing decorative.
- Light theme only. Dashboards are internal, desktop, and screen-shared with clients.
- Status is never shown by color alone. Always pair color with text, a shape, a check mark or weight.
- Desktop first. Check every screen at 1440px and 390px. Content max width 1440px, centered. On phone the Engine covers Home only (see Phone layout).
- Nothing on screen that a client should not see (for example fees).

## 2. Color tokens

| Token | Hex | Use |
| --- | --- | --- |
| `--navy` | `#000523` | Accent: primary buttons, selected states, titles (and the table header in client-facing exports) |
| `--sky` | `#C6E1EE` | Borders of light blue elements, focus ring, text on navy (secondary) |
| `--sky-soft` | `#EAF3F8` | Row hover, current step, banners, light badges |
| `--page` | `#F5F5F5` | Page background and top bar (brand light grey) |
| `--surface` | `#FFFFFF` | Cards, tables, inputs, panels |
| `--ink` | `#1A1A1A` | Body text |
| `--subtle` | `#707780` | Nav group labels: the lightest grey that still passes 4.5:1 on white. Nothing else. |
| `--muted` | `#5E6670` | Labels, secondary text, "Not set" (passes contrast on white and on #F5F5F5) |
| `--line` | `#E4E4E7` | Card and input borders, dividers |
| `--line-strong` | `#C9C9CF` | Stronger dividers, dashed empty states, arrows |
| `--column` | `#FAFAFA` | Kanban columns: between the white cards and the `--page` grey, so columns read as lanes |
| `--alert` | `#8A1C1C` | Overdue, errors (always with text) |

Brand colors not used as UI tokens: off-white `#F7F5F0` (print and slides), grey `#9A9A9A` (fails contrast for text on white).

## 3. Typography

- Inter only, for every element. Self-host it (`@fontsource-variable/inter`) and set it on `html` so every element inherits it, form controls included (`button, input, select, textarea { font: inherit; }`).
- No serif, no second family, no monospace for data.

Four sizes only, so each step is visible: 20, 15, 13, 12. Big numbers reuse 20.

| Role | Size | Weight | Color |
| --- | --- | --- | --- |
| Page title | 32px, letter-spacing -0.03em, line-height 1.25 | 600 | navy |
| Page fact line (under the title) | 13px | 400 | muted |
| Card title, drawer title | 16px | 600 | ink |
| Section heading inside a card or drawer | 13px | 600 | ink |
| Body | 13px, line-height 1.5 | 400 | ink |
| Row title (sender, task, item title, deal name in a cell) | 13px or 12px in tables | 500 | ink |
| Tables, chips, badges, form labels, small labels | 12px | 400 (table headers 600) | ink or muted |
| Nav group labels | 12px | 400 | subtle |
| Big numbers (funnel counts, KPIs) | 20px, line-height 1.2 | 600 | ink |

- Weight 600 marks titles and the selected item only. Rows use 500 so they do not compete with titles.
- Navy text is for the page title, links, selected states and text on sky. Card titles are ink, so they do not compete with buttons.

- Nothing smaller than 12px. Exceptions: the 10px stage names in the process tracker, and a decorative icon glyph hidden from screen readers.
- Numbers in tables and counters use `font-variant-numeric: tabular-nums` and are right-aligned.
- Sentence case everywhere. No all-caps labels.

## 4. Layout and spacing

- Spacing scale in 4px steps, as tokens: `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-5` 20px, `--space-6` 24px, `--space-8` 32px. Every margin, padding and gap uses one of them. Exceptions: 1px and 2px inside chips, badges and focus rings.
- Page: full width beside the nav (no max width, so tables use wide screens), 32px side gutter (16px on phone), 24px top padding, 16px bottom (no empty band under the last card).
- Every page fits the screen from 768px up: the page title and the filter row (and Buyers or Sellers search's selection bar) stay fixed; everything below sits in one page body that fills the rest. A single table card in the body scrolls inside with its header row stuck to the top; pages of cards scroll the body. The Pipeline board fills the height and each stage column scrolls. On a very short screen the whole page scrolls instead.
- Popovers inside a scrolling area (row "..." menus, Home status chips) open at page level, fixed under their trigger, and open upward when less than 200px is left below. A scroll or resize closes them.
- Cards stack vertically with 12px between them.
- Card padding: 20px 24px (16px on phone; 12px 24px for the tracker and the funnel).
- List rows (tasks, emails, agenda, feeds): 8px top and bottom.
- Group related lists inside one card with 20px between sections and a 13px section heading, instead of a card per list.
- Corners: 8px on cards, 6px on inputs, buttons, tables and small boxes, 4px on tracker cells, full (999px) on chips and badges.
- Shadow: only a faint one on cards, `0 1px 2px rgb(0 5 35 / 0.04)`. Dropdowns `0 8px 24px rgb(0 5 35 / 0.08)`. The side panel `-12px 0 32px rgb(0 5 35 / 0.1)`.
- Label and value grids: 3 columns, each item a 120px label column plus the value, 12px row gap, 40px column gap.

## 5. Components

### Top bar
- Same grey as the page (`--page`), 60px high, 1px bottom border (`--line`). No colored bar.
- Left: the Wusool Capital logo, 24px high. The logo file is the white line version (`logo line white.png`); on the light bar draw it dark with `filter: brightness(0)`.
- After the logo: a 1px divider (`--line-strong`) and the product name in muted text.
- Right: plain text links (ink, underline on hover) and controls such as a select, 24px apart.

### Cards
- Soft look (11 Nov 2026): white, no border, 16px corners (`--radius-card`), two-layer shadow `0 1px 2px rgb(0 5 35 / 0.04), 0 8px 24px rgb(0 5 35 / 0.04)`. One card per page section.
- Page head: the title, then one muted fact line when the page has a firm-wide fact (Pipeline: "14 deals · 12 active · $160M in active deals"). The line does not move with the filters.

### Buttons
- Height 36px, padding 0 16px, pill corners (`--radius-pill`, 999px), weight 500, no wrap.
- Primary: navy fill, white text.
- Secondary ("quiet"): white fill, `--line` border, ink text; hover `--page`.
- Small: height 28px, padding 0 10px, 12px text (for example "View" next to a link; shown disabled when there is no link yet; "Share" at the right of the page title, copying the page link with a "Link copied" note beside it).
- Disabled: opacity 0.45, not-allowed cursor.
- Text-style actions: navy underlined text with no box (for example "Clear filters", "Remove").

### Inputs, selects, search
- White, 1px `--line` border, 10px corners (`--radius`), 36px high, 0 12px padding. One-line search boxes (the text search at the start of a filter row, the describe box on Search and Multiples) and the filter buttons are pills, with 16px side padding in the describe box; form fields in drawers keep 10px corners; the segmented switch is a pill track with pill options.
- Selects drop the OS arrow (`appearance: none`) for a 14px Phosphor CaretDown in `--muted`, 12px from the right edge, with 32px right padding so text never runs under it.
- Focus: navy border plus a 2px `--sky` outline.
- Label above the field in 12px muted text, error below in 12px `--alert`. Invalid field gets an `--alert` border.
- Placeholder text in `--muted`, never used as the label.

### Badges and chips
- An editable chip opens a small menu of its values under it (white, 1px border, 6px corners); the current value is highlighted in `--sky-soft`, and picking one saves at once.
- Pill shape, 2px 10px padding, 12px text, 1px border.
- Badge (for example "Sell-side"): `--sky` border, `--sky-soft` fill, navy text.
- Status chips in three tones, always with their text:
  - Not started: `--line` border, muted text.
  - In progress: `--sky` border, `--sky-soft` fill, navy text.
  - Done: navy fill, white text.
- Status dots (11 Nov 2026, replaces the soft-fill status pills; class `.pill`): a 6px round dot, 6px gap, then the status text in 12px ink. Never the dot alone.
  - Not started or unknown: an empty ring in `--line-strong`.
  - Contacted: `--muted`.
  - Talks: `--pill-talks-ink` (`#6E4A00`).
  - LOI: `--sky` with a 1px navy ring.
  - Due diligence: navy.
  - Bidding: `--pill-bidding-ink` (`#46297A`).
  - Closed: `--pill-closed-ink` (`#1C5532`).
  - Passed: `--alert`.

### Tables (brand table style)
- Grouped tables (Outreach): rows are plain white with a 1px `--line` between them, no stripes; each group header is a `--page` grey bar with `--line` borders above and below, label 12px semibold ink and its count muted. The bar never looks like a row.
- One line per row (8 Nov 2026): no muted second line under a name. A fact that matters gets its own column or sits beside the main value (an "NDA" chip next to the status, "Yesterday 21:40, 6 files"); anything else lives in the drawer.
In the Engine (11 Nov 2026) tables use a light header so the rows lead and navy stays for actions. The brand guideline's "Illustrative Exit Summary (AED '000)" table, with its navy header, stays for client-facing output: exported PDFs, teasers, CIM tables and slides.
- Header row: white background, `--muted` Inter 12px labels at weight 500, padding 10px 12px, one 1px `--line` hairline below, no wrap. The sorted column and a hovered label turn ink. Each label is a button that sorts: first click A to Z (numbers low first, dates newest first), second click reversed, third click back to the default order. The sorted column shows ↑ or ↓ and `aria-sort`.
- Header labels 12px, weight 500, padding 12px.
- Data rows (11 Nov 2026): white, split by a 1px `--line` hairline; no stripes, no column lines.
- Cells: 13px, padding 14px 12px (about 48px rows), vertically centered.
- Numbers right-aligned in tabular figures. Text left-aligned.
- Table corners follow the card (16px) with `overflow: hidden`; `border-collapse: separate; border-spacing: 0`.
- Clickable rows: pointer cursor, `--sky-soft` hover, keyboard focus outline (2px navy, inset), and Enter opens the row.
- Wide tables: `table-layout: fixed` with set column widths; one line per cell with `…`, and the full text in a `title` tooltip. Keep headers, statuses, dates and numbers whole; let free text be cut.
- Empty values: "Not set" in muted text.
- Long tables in a card: card `max-height: calc(100vh - 32px)` as a flex column; the table sits in a scroll box that clips the corners, with `thead th { position: sticky; top: 0 }`. The box only scrolls once the card is 16px from the top of the window (a scroll listener sets `data-pinned`), so the wheel moves the page first and the rows after.

### Process tracker (stages)
- PRD MV2 style, chosen 7 Nov 2026: one bar per stage in a row (CSS grid, 4px gap), each bar 6px high with 999px corners, the stage name under it in 12px.
- Done and current: `--sky` bar fill; the current stage's bar is navy and its name is semibold navy with `aria-current="step"`. Upcoming: `--line` bar, muted name.
- Status is never colour alone: the current stage name is bold and a visually hidden "completed", "current stage" or "not started" follows each name.
- A banner above for side states (for example "Mandate on hold"): `--sky-soft` fill, `--sky` border with a 4px navy left border, navy text.

### KPI or funnel counters
- A row of equal boxes, white, 1px `--line` border, 6px corners, padding 6px 12px; card padding 10px top and bottom.
- Inside: label 12px muted on top; below it on one line, number 16px semibold and secondary value (for example a percentage) 12px muted.
- Small arrows between boxes in `--line-strong`.
- Clickable counter selected: navy fill, white number, `--sky` labels, plus `aria-pressed="true"` and a text note elsewhere ("Funnel: Replied").

### Filters toolbar
- One row, 10px by 12px gaps, items 36px high: search box, dropdown filters, segmented control, checkboxes. No result count while nothing is filtered; once a filter hides rows, the count sits in the button that undoes it: "Clear filters (4 of 18)".
- Segmented control: `--line` track with 2px padding (so it shows on the grey page), options in muted text; the selected one white, semibold navy, with a small shadow.
- Every segmented switch slides (`ui/segmented.tsx`): one white thumb moves under the options in 320ms with a strong ease in and out (`cubic-bezier(0.65, 0, 0.35, 1)`) when a tab is picked (left and width), the text colour moves with it, and the new tab's content fades in over 200ms. No motion when the user prefers reduced motion.
- Dropdown filter (every list page: Pipeline, Deal view Buyers and History, Buyers, Sellers): a 36px button reading the filter name ("Sector") with a CaretDown, or the applied value when set ("Sector: Dental +1", "EBITDA: from $1M"). Applied: navy border, `--sky-soft` fill, navy 500 text.
- Its panel (264px, white, dropdown shadow) holds a draft: a list filter has a "Type a sector" box (when over 6 options) and checkboxes; a range filter has Min and Max fields in $M. Footer: Clear (quiet) and Apply (primary). Nothing changes until Apply. Options never repeat the filter name.
- Every list panel starts with "All" (ticked when nothing is picked), divided from the options by a 1px `--line`.
- A filter can have a default (Pipeline: Owner is me, Status is Active). Ticking All shows "Owner: All". Clear filters shows everything.
- Panels close on a press outside them or Escape, never on a click inside (clicking an option's text ticks it).
- "Clear filters" (36px quiet button, same height as the filters) appears once any filter is applied.
- Active special filter: a navy outlined pill with its name.

### Side panel (row details)
- Right drawer floating 12px inside the window (top, right and bottom), 16px corners, half the window wide (640px minimum, full width less 24px on phone), white, light navy scrim behind (`rgb(0 5 35 / 0.2)`).
- Header: title, an optional status line with facts only (sector and city, a date, a source; never an explanation), Save (primary) and Close (secondary). A button names its effect when that matters ("Save to Attio", "Publish to website"). Notice bar under the header in `--sky-soft` when an action is blocked.
- Title 16px semibold ink. Body scrolls; sections separated by 1px `--line`, 20px 24px padding, 13px semibold ink headings.
- Opens with a 180ms slide and fade, skipped when the user prefers reduced motion.
- Escape closes; ask before discarding unsaved changes. Focus moves into the panel and back to the row on close.

### Left nav (Engine)
- Fixed column, 232px wide, white (`--surface`), 1px `--line` right border, full height, scrolls on its own.
- Each link returns to its page as you left it (filters, view, open item, a search already run and its sentence), because the Engine remembers the last URL per page and per section (`lib/page-memory.ts`) until the browser tab is reloaded. Search's Buyers | Sellers switch returns to each side's last search.
- On Search and Multiples, Clear filters also drops the results and the describe sentence, so the page starts over.
- Top: one lockup across the full nav width: the logo (links to Home) takes the width "Engine" leaves (about 21px high), then a 1px `--line-strong` divider and "Engine" in muted 15px; the "Demo" badge sits under it with 12px above and below while the app runs on demo data. 16px top padding. On phone all three sit in one row (logo 18px high, Engine 13px).
- Firm group order: Multiples, Scorecards, Referral partners, Engine optimization, Reports. Reports and GitBook are external links that open in a new tab.
- Groups: Work (Home, Pipeline, Outreach), Lists (Buyers, Sellers, Search), Firm, Settings, separated only by a 1px `--line` hairline inset to the item text, 12px above and below. No visible group labels (8 Nov 2026: a label at the links' size read as one more link); each list carries its group name as `aria-label` for screen readers. The whole nav fits a 700px window without scrolling.
- Items: a 16px Phosphor icon in `--muted` (navy on the current page), 10px gap, then the label in 13px ink, 24px line height, padding 4px 8px (32px rows), 4px between rows, 10px corners. Icons: House, Kanban, PaperPlaneTilt, Briefcase, Storefront, MagnifyingGlass, Calculator, Target, Handshake, Gauge, Newspaper, FileText, BookOpen. The nav fits a 13-inch laptop window (700px tall) without scrolling; shorter windows scroll the nav. Hover `--page`, fading in over 150ms ease-in-out (none for reduced motion). Current page `--sky-soft` fill, no motion, navy semibold text, `aria-current="page"`.
- External links (GitBook) open in a new tab, with "(opens in a new tab)" for screen readers.
- No collapse control: the nav is always open on desktop.
- Bottom row, pinned to the foot of the nav above a 1px `--line` divider: profile on the left (28px initial avatar in `--sky-soft` with a `--sky` border, name semibold, job title muted 12px on one line; opens Profile) across the full width. Log out sits on Profile beside Edit, so the job title fits on one line. Hidden on phone.
- The Engine has no separate top bar on desktop; the nav carries the logo.

### Phone layout (under 768px)
- The left nav becomes a 56px top bar: logo on the left, a single "Home" link on the right. 16px side gutter.
- Only Home has a phone layout. Every other page shows one card: "Open this page on a computer" and a Go to Home button.
- No horizontal scroll at 390px.

### Home layout (Engine)
- Two full-height cells that fill the screen at 1200px and wider, so the page never scrolls; each cell scrolls inside. 12px gap. Your day on the left (morning brief, then today and this week as a time rail; the end of day check from 17:00); Actions on the right (Emails | Approvals | Workstreams). Emails has two lists, "To reply" then "To send", each named by a 13px heading; Approvals has record changes only; a tab with one list shows no heading. No to-do list: tasks live in Attio. The deal feed and mandates live in Pipeline and the Deal view, the scorecard on Scorecards.
- Cell: white card, 16px 20px padding, a head with the 16px title and, for tabbed cells, a segmented control on the right whose options carry their counts ("Review 4"); a 1px `--line` under the head. The body scrolls, with a 24px fade at the bottom and 24px bottom padding so the last item clears it. Cards placed in a cell lose their own frame.
- Header: "Home", the date, and the scorecard strip on the right: a white pill with "Scorecard", one 10px RAG dot per metric (green, amber, red) and "2 on track, 1 at risk, 1 behind". It links to Scorecards.
- Time rail: a 2px `--line` rule on the left of each day's list; a 10px navy ring per meeting, a navy diamond per deadline, level with the first line.
- Mandate rows: code name (500), stage and last activity muted, a nine-step stage bar (6px segments, navy up to the current stage, `--line` after), "Next: ..." in 12px muted. The row opens the deal page.
- Under 1200px the cells stack and grow with their content. On phone only Actions shows (Emails | Approvals); the scorecard strip hides.
- Card head: section title, optional badge, and a muted 12px count or source pushed right ("4 to review", "From Notion").

### Workstream row (Home)
- Columns: Workstream (the name in 500, then "Due 13 Nov 2026" in 12px muted, both clickable to edit), Status (fixed 136px for the status chip), Next step (clickable to edit), and a 44px column with the row "..." menu. Every edit is click, change, Save; Escape cancels.
- Delete: "..." then "Delete workstream" turns the row into one line, "Delete <name>? It moves to Notion's trash." with Delete (primary small) and Cancel. Three clicks, no second layer.

### To-do row
- One line on desktop: checkbox, title (cut with "..." when space runs out), then on the right in 12px muted the overdue mark when late, the deal and "Due 9 Nov 2026". On phone the right part wraps under the title.

### Actions rows (approvals and action emails)
- Two lines, two text styles. Line 1: what to act on in 13px ink 500, cut with "..." on one line, and the actions on the right of the same line. Line 2: a small chip, then one 12px muted line of context cut with "...". 12px between rows, 1px `--line` divider.
- Approval: a click anywhere on the row opens the side panel (full draft, evidence, source); hover underlines the title in navy. Line 1 is the title with Approve (or "Approve and send" for emails; "Generate email" for follow-ups, which opens the panel with the draft written; primary small) and Reject (quiet small button with a 12px Phosphor X before the word). The panel of a follow-up opened from the row shows the reason and a Generate email button first; Send stays off until there is a draft. Line 2: the kind chip (Email draft, Follow-up, Stage change, Tasks, Next step) and one sentence of context (recipient and message, stage move and evidence, first task and how many more).
- Action email: the whole row is one link to the reply drawer. Line 1: sender (600) and subject, then the time (with the overdue mark when due) and a Reply button. Line 2: the deal badge (or a "No deal" chip), the sender's company and the suggested action.
- No "AI drafts" badge in the Actions header; the AI draft badge shows in the side panel next to the draft itself.
- The codename check replaces line 2 with a 12px `--alert` 600 line: "Remove "<client name>" before sending. Buyers only see the code name." and disables Approve.

### Activity feed item
- One row per event: text on the left (actor or deal in 500), time on the right in muted 12px, 1px `--line` divider. Static: no hover.

### Status chips added for the Engine
- Blocked (workstreams) and Behind (scorecards): white fill, `--line-strong` border, semibold `--alert` text.
- On track uses the Done tone, At risk the In progress tone.
- Pressed toggle (for example tools picked in the end of day check): navy fill, white text, `aria-pressed="true"`.

### Toast
- One-line confirmation after an action, fixed at the bottom center: navy fill, white 13px text, 6px corners, `role="status"`. Fades out after 8 seconds; no fade when the user prefers reduced motion. Demo sends say "Demo: nothing was sent."

### Deal view (deal page)
- Reached from the Pipeline quick view ("Deal view") at `/deals/<id>`. Pipeline stays highlighted in the nav. Above the card, a 12px muted "< Pipeline" link (Phosphor CaretLeft) returns to the board or list it came from, filters included.
- Overview card, compact and fixed above the tabs (8 Nov 2026), 16px padding top and bottom: one row with the code name as the page title, the side badge, client name and lead advisor, and "Edit" and "Email client" (quiet) on the right.
- One line of figures 12px under it: label 12px muted, value 13px semibold tabular, margin or multiple muted beside it (Revenue FY2025, Gross profit, EBITDA, Asking price). Missing values read "Not set". No fees. "See multiples" (link) at the right end of the line.
- No client advisers block (removed 7 Nov 2026: names found in mail would be guesses).
- No scroll motion. The overview, the tabs and each tab's toolbar (search, filters, Find more) stay fixed; only the content under them scrolls (a table inside its card with a sticky header row, the History timeline inside its card, the Materials grid in the page body).
- Stage tracker last, always visible, above a `--line` hairline with 12px either side, so it sits right above the tabs. 8px between each bar and its name. Each name carries the days spent in that stage in brackets ("Outreach (22)"); upcoming stages have none. Each stage is at least as wide as its label, so nothing wraps or is cut. No next-step line: the next step is pinned in History and edited in Edit.
- Tabs under the card: muted 13px labels, selected one navy semibold with a 2px navy underline, `role="tab"`. "Buyers" reads "Targets" on buy-side deals.
- Every drawer is named in the URL (`?panel=buyer:c-arcadia`), so links open it directly.

### Counterparty status pills
- Status dots (see Badges and chips): Not contacted ring, Contacted grey, Initial conversations amber, LOI sky, Due diligence navy, Bidding offer violet, Closed green, Passed red. Always with their text.

### Material card
- Seven cards in deal order (Proposal, Client NDA, Engagement contract, Financials, Teaser, CIM, Data room) in an auto-fill grid of 240px minimum, 16px gaps. White card, 1px `--line` border, 8px corners, 16px padding, 12px between lines. The whole card is one button that opens its drawer; hover `--sky-soft`.
- Lines: name 14px semibold with the status chip on the right (Not started outlined, Drafted and Sent sky, Signed, Approved and Live navy), then one line: the date or version once every item is in hand; otherwise a 6px bar (navy fill on `--line`) with "N to ask the client" (alert dot, 12px semibold `--alert`) or "N of M in hand" beside it.
- Drawer: checklist in two groups, "From the client" and "From us", each heading with its count; each item a 16px check box (navy when in hand), name, "In hand" muted or "Missing" in `--alert` semibold, and its reason in muted 12px; 12px padding per row. Then the client email (AI draft badge, editable), Draft in Claude (prompt box, "Open in Claude" small primary, "Copy prompt" quiet), and for agreements Main terms and Fee terms behind "Show terms". Footer: Send request (primary when items are missing), then the one status move.

### Credit box (Apollo)
- `--sky-soft` fill, `--sky` border, 6px corners: what the enrichment finds, its cost in credits and the credits left, then the button "Enrich for N credits". Enrichment never runs without this click.

### History timeline
- Pinned next step on top: one row in a plain card (12px by 16px padding): "Next step" muted 12px, the step in 13px 500 cut with "...", then owner and due date muted 12px on the right.
- Events in one card: time on the left (muted 12px tabular, 128px column), then type (muted 12px), text, and "Source: ..." in muted 12px. Decision events get a `--sky-soft` band and a navy line "Decided by <name>: <why>".

### Outreach
- Toolbar: a segmented control, All | Buyers on my deals | Owners to approach (owners you ask whether they would sell, before any mandate), and the company count on the right.
- No tiles: the list is grouped by state (Due today, Waiting for a reply, Replied, No contact), each group header with its count. One line per row: Company, Deal or list, Contact, Status (for example the overdue mark, then "Follow-up 1 of 2, 10 Nov 2026"), Last message, one action.
- One brand table with a section heading row per state (13px semibold ink on white, muted count): Due today, Waiting for a reply, Replied, No contact, No reply after both follow-ups. Empty sections are hidden. Rows: Company (name 500, deal code name or list muted), Contact, Status in words ("Follow-up 1 of 2, due today", the overdue mark with "was due 10 Nov", "Sent 9 Nov, follow-up 1 of 2 on 13 Nov", "Replied 9 Nov, next: ..."), Last message cut with "...", and one row button: Follow up or Write message (primary) when due, Find contact or Open (quiet) otherwise. Row and button open the same drawer.
- The states come from one rule (`lib/outreach-state.ts`), so a tile count always matches its section.
- Each section header is a toggle across the full row: a 12px muted chevron (down when open, right when closed), the name and its count. Due today, Waiting for a reply and No contact start open; Replied and No reply after both follow-ups start closed. Open and closed sections are kept in the URL (`closed=`), so the page returns as it was left.

### Pipeline quick view: contacts and Next
- Contacts: one row per person in four columns: name (500) with title and company in 12px muted under it, email (mailto link), phone (tel link), Remove. Missing email or phone reads "No email" or "No phone" in muted. Hairline between rows.
- Next: one muted line on why (for example "Follow-up was due 10 Nov 2026.") and one primary button named for the action ("Follow up with Gulfstone Partners", "Draft the client NDA"). It opens the Deal view on the panel where the action is done. The footer link reads "Deal view".

### Kanban board (Pipeline)
- One 240px column per stage, all ten in order (Engaged sits between Qualified and Mandate signed), scrolling sideways. "New deal" (primary) at the right of the filter row. Filters: Side (Sell-side, Buy-side), Owner, Status. Passed and On hold are reached through the Status filter, not columns.
- Column: `--column` fill, no visible border (transparent, navy while a card is dragged over), 16px corners, 12px padding, 360px minimum height. Header: stage name 13px semibold ink with the count in muted tabular figures on the right. Empty column: "No deals" in muted 12px.
- While a card is dragged over a column: `--sky-soft` fill and navy border (the only motion is this state change).
- Dragging is a shortcut. The Stage field in the quick view does the same for keyboard users.

### Kanban card
- White, no border, 12px corners, the card shadow, 12px padding, 4px between lines. The whole card is one link that opens the quick view; hover `--sky-soft` fill and a 1px `--sky` ring.
- Lines: code name (500), side and sector (muted 12px), "Next: ..." (muted 12px, two lines max), then value in tabular figures on the left and the owner's 24px initial avatar on the right.
- Never a fee on a card.

### Engagement letter panel (inside the Engagement contract card)
- Opened by "Draft contract" on the Engagement contract card in Materials. Replaces the card's panel content (Back returns to the checklist), so the page keeps one layer.
- No header status line; fees are behind this form only.
- Terms in a two-column form grid, defaults from the Wusool skills. Sell-side deals choose "Structured sale process" or "Platform listing" with a full-width segmented control.
- Fee example box: `--sky-soft` fill, `--sky` border, navy 12px label, one line per worked example computed in code; a warning line in `--alert` when the retainer would exceed the fee.
- Sell-side only: a "Confidentiality agreement" section with the company's legal details (prefilled from the deal), the company signatory, governing law and competitor sectors. Missing required fields show the 12px `--alert` line "Needed for the confidentiality agreement." and block Send.
- Documents list (name left, skill name muted right). When terms change, an "Out of date" chip and an "Update documents" button appear and Send is disabled until updated.
- Email section: recipient line, Subject, Message, "AI draft" badge. The email never states fees.

### Icons
- Phosphor (`@phosphor-icons/react`), one family, regular weight unless noted. Never hand-drawn SVG.

### Actions menu ("...")
- An icon button with Phosphor DotsThree (bold), white with a `--line` border: 28px on table rows, 36px in a drawer header so it matches Edit and Close. Screen readers: "Actions for <name>".
- Its list opens under it, right-aligned, as wide as its longest label so every action stays on one line (8px 12px per option). Every row action stays at 3 clicks: menu, action, then Save, Add or Send.
- A menu is not a dialog, so it does not count as a second layer. Picking an action opens the drawer with that panel, or swaps the open drawer's content (Back returns to the record).

### Buyers universe
- Filter buttons: Sector, Geography, Type (lists), Check size and Min. EBITDA (ranges in $M), stored in the URL.
- Brand table: Buyer (name 500, HQ muted under it), Type, Sectors, Geography (cut with `…`), Check size (right-aligned, "$10M to $40M"), Key contact (name, title muted), Owner, Status pill, then the actions menu.
- "Add buyer" (primary) at the right of the filter row opens the edit form empty, with Name, HQ city and Website first; a website already in Attio is not added twice.
- Buyer status pills reuse the counterparty tones: Active green, Dormant outlined, Do not contact red. Always with their text.
- Check size is what the buyer pays per deal (Attio `check_size_min/max`); Min. EBITDA is the smallest target profit it looks at (Attio `ebitda_floor`). Shown in USD; the Toolkit converts Attio's AED at the 3.6725 peg.
- Record drawer is read only: Profile (label grid, with Check size and Min. EBITDA, then the notes 16px below in muted text, 65ch max), Contacts (first is the key contact), Deals (code name, counterparty status pill, last contact). Add to a deal is blocked with a notice while the buyer is "Do not contact".

### Text search (Universes)
- First item in the filter row: a 240px field with a Phosphor MagnifyingGlass inside on the left and a short placeholder ("Name, contact or note"). It filters as you type (no Apply, no AI), combines with the filter buttons, and keeps the words in the URL. Buyers match name, HQ, sectors, notes and contact names; sellers match name, HQ, sector, notes and owner names.

### Sellers universe
- Same layout as the Buyers universe. Filters: Sector, Geography, Revenue, EBITDA (ranges in $M), Open to selling.
- Brand table: Company (name 500, HQ muted), Sector, Geography, Revenue and EBITDA (right-aligned, "$6M"), Owner contact (name, title muted), Appetite pill, Re-engage date ("Not set" muted), Owner, actions menu.
- Open to selling pills (Attio `appetite_signal`) reuse the counterparty tones: Unknown outlined, Interested amber, Warm intro green. Always with their text.
- Record drawer is read only: Profile, Contacts (first is the owner contact), Outreach (last message on the seller's list entry), Deals (buy-side mandates where it is a target).
- Actions menu: Ask if open to selling (AI draft, Send; greyed out in the menu unless Open to selling is Unknown, and blocked with no contact or when already approached), Add to a buy-side deal, New sell-side lead (the shared lead drawer), Edit profile.

### Search (buyers and sellers)
- One page, `/search/buyers` and `/search/sellers`, with a Buyers | Sellers segmented switch beside the title (links, so each side keeps its own route). Then the describe box, then the filter buttons and a primary Search button. Nothing shows before the first search (each run is a paid Toolkit and Apollo call once live).
- Selection bar above the results, in a white bordered strip: "N selected", "Enrich for N credits" (quiet) with the credits left, "Add N as buyer roles" (primary), a deal select with "Add to deal", and "New buy-side lead" (one row only, opens a drawer with code name, sector and city).
- Buyer results: checkbox column (header checkbox selects all), Company, Type, Sectors, Geography, Check size, Why (the match reason, cut with …), Attio ("In Attio" badge or muted "New"), Contacts ("Not enriched", "Held in Attio" or the names found). One line per row; clicking a row ticks it.
- Companies in Attio can be ticked for Add to deal but are never added again as buyer roles (matched by domain).


- Seller results: Company, Sector, Geography, Revenue, Employees, Why, Attio, Owner contact ("Not enriched", the name, or muted "Asked 4 Nov 2026"). Filters: Sector, Geography, Revenue.
- The shared selection bar (`ui/search-actions.tsx`) adds "Ask if open to selling" (primary, small).
- Ask owners drawer: one section per owner with a checkbox, the company name, "AI draft" badge, "To <name>, <title>" and the editable note. Owners already asked, or without a contact, sit under "Not included" with the reason. One "Send N notes" button.

### Scorecards
- One person at a time: a segmented control with each person's name (default: me), the week on the right. The card title is the name, its meta "2 of 5 working days done", and "Edit scorecard" (small quiet) on the right.
- This week: one tile per metric (white, 1px border, 8px corners, 16px padding, auto-fill 260px minimum): label 12px muted, the actual 28px semibold with "of <target>" 15px muted, the RAG pill, then the tagged people as rows (name 500 and company muted on two lines, both cut with `…`, a 24px round remove button with Phosphor X, hairlines between rows), then "Tag a person" (calendar suggestions, then search). No charts.
- Yes or no metrics (LinkedIn schedule followed): the value "Yes" or "No" and a Yes | No segmented switch; On track once Yes, At risk until then.
- RAG pills from the pace rule in `lib/scorecard.ts`, reusing the pill tones: On track green, At risk amber, Behind red. Always with the word (Home uses the same pill).
- "Last 8 weeks" table, newest week first: metric with "(target N)" muted, then each week's actual in semibold, green (`--pill-closed-ink`) with a Phosphor CheckCircle at or above target, `--alert` red below it. Yes or no weeks read Yes or No. A metric added later reads "Not tracked" for older weeks.
- Edit scorecard drawer: one row per metric (Metric name, Type Count or Yes or no, Weekly target, Remove), then "Add metric". Save writes the person's own list.

### Referral partners
- Grid (default) or List, switched by the segmented control before the filters. Grid: auto-fill cards of 280px minimum (white, 1px border, 8px corners, faint shadow, hover `--sky-soft`): logo, name (600, the keyboard target) and category, the "..." menu, the offer, the referral in 12px muted, then the Status pill and "2 leads, 2 open". "Add partner" (primary) at the right of the filter row opens the edit form empty, with Name and Category first.
- Logo placeholder until Sanity logos: the initials, navy 600, on a `--sky-soft` square with a `--sky` border and 6px corners (40px in cards, 28px in the list).
- Filters: Category, Status (Active, Inactive: listed on the website or not). List: brand table with the small logo beside the name, Partner (name 500, category muted), Offer, Referral, Locations, Leads, Open (tabular), Status pill (Active green, Inactive outlined), actions menu.
- Record drawer (same header as Buyers and Sellers: Edit, menu, Close): Website profile, Internal terms behind "Show terms" (they are fees; the page stays safe to screen-share), Leads referred (code name, client, stage chip, owner, last activity, next step).
- Edit and publish: website fields, a "Preview on the website" card (white, 1px border, 8px corners, max 360px: category muted, name 16px semibold, description, offer in navy 500), then Internal terms marked "Never published". The button says Publish.

### Engine optimization
- Weekly summary card on top: bullets computed by rules, "Copy summary" (small quiet) copies them for the meeting notes.
- Two-column grid of cards (one column under 1200px): Missed follow-ups (overdue mark, "Was due"), Clients waiting 7 days or more. Then Time in stage (days against the median, "N days over" with the alert dot, or muted "Within median"), Reply rate by template and sector, Conversion per stage ("Lead to Qualified").
- Cards side by side in the grid start level (no stacked-card top margin) and stretch to the taller one, so both edges line up.
- Bottlenecks: one row per entry (what, then who, when, where and deal in muted 12px), "Make Notion issue" (row button) or an "In Notion" chip.
- "Log bottleneck": a primary button at the right end of the Engine optimization header. Its drawer asks what broke, where (first option preselected) and which deal; Save is the second click.

### Describe box (Search, Multiples)
- One full-width 40px input above the filter row, no heading, no button, no helper line. The placeholder carries the instruction and an example ("Describe the buyers you want, for example family offices in the UAE buying nurseries, then press Enter").
- Enter fills the filter buttons (and the keywords from what is left of the sentence) and runs the search. The filled filter buttons switch to their selected style with a 200ms colour transition, so the person sees what changed and can adjust them. No separate keywords field.

### Multiples
- "Ask in plain words" card: one input and "Fill filters" (quiet). It only fills the filter buttons; results run on "Show results" (primary), like the search pages.
- Filter row starts with an EV/EBITDA | EV/Revenue segmented control, then Sector, Geography, Deal size, Year, Deal type.
- Database card: three figure boxes (Median, Range "6.9x to 8.4x", Comparables used "3 of 3"), then the brand table with a checkbox per row; an unticked row is struck through in muted text and leaves the median. Multiples as "7.4x".
- "Unverified web results" card (only under 5 database matches): same table, the source as a link, and "Save to database" (row button). Never counted in the median.
- On the deal page, a 12px "See multiples for <sector>" link under the figures opens this page prefilled.

### Skills
- Category filter, then a brand table: Skill (title 500, file name muted), Category, Version (tabular), Last edit (date, who muted), Used in.
- Drawer: File and Used in, the instructions as notes, then Versions (version bold, note, who and date on the right, newest first). Edit only for admins; others see "Only admins can edit skills." Edit asks "What changed" before Save.

### Profile
- Head card: 44px initial avatar beside the name (16px semibold) and title (muted), "Edit" and "Log out" (small quiet) on the right, a `--line` divider, then one row of four facts (Email, WhatsApp, Role, Access) with 12px muted labels above ink values.
- Both cards stay put; the accounts table scrolls inside its card under the card title, header row stuck (desktop).
- Connected accounts card: "N connected, N needs attention, N not connected" as the meta and "Add connector" (small primary) at the top right. Table sorted problems first: Service (name, what the Engine uses it for), Account, Status pill (Connected green, Needs attention amber with the reason in 12px `--alert` under it, Not connected outlined), Last sync, then one row button: Reconnect or Connect (primary), Disconnect (quiet).
- Add connector drawer: one row per available service with Connect.
- Edit profile drawer: Full name, Title, WhatsApp, then Save. Email comes from Google sign-in; role and access are set by an admin.

### Charts
- Bars: one series per chart in navy, 4px rounded top, flat on the baseline, at least a 12px gap between bars; no axis or grid, since the target line and the tile number carry the scale.
- Target: a 1.5px dashed `--muted` line across the chart, named in the caption ("Dashed line: target 5").
- Hover: the whole column is the hit area; the hovered bar turns `--sky` with a navy outline and the caption reads "Week of 28 Sept 2026: 5 against 5". One series means no legend; the tile title names it. Every chart has a table view beside it.

### Row buttons
- Buttons inside table rows and review lists share one width (`.button--row`, 120px), so a column of buttons lines up whatever the label.

### Record drawer header (Buyers, Sellers)
- Title and an optional factual status line on the left; on the right Edit (quiet), the 36px "..." menu with the other actions, and Close, all 36px high.
- Last section "Emails": one line per Gmail thread with the company, subject on the left (cut with `…`), date right in muted 12px tabular figures, newest first, 1px `--line` between lines.

### Empty and missing states
- Empty list: a white box with a dashed `--line-strong` border and one short muted fact ("No offers yet."). No instructions: the action that fills it is already on the page.
- Missing value: "Not set" in muted text. Unconfirmed value: "To confirm" in muted text, with the stored value in a tooltip.

### Overdue and warnings
- A small `--alert` circle with "!" plus the word "Overdue" in semibold `--alert`, above or before the date. Never color alone.

## 6. Accessibility

- Visible focus on everything: 2px navy outline, 2px offset (inset on table rows and segmented options).
- Labels on every input; errors tied to fields with `aria-describedby`.
- Body text contrast at least 4.5:1 (that is why muted is `#5E6670`, not the brand grey).
- Respect `prefers-reduced-motion`.

## 7. Writing in the UI

- Simple words, sentence case, no em dashes, no filler adverbs or marketing words.
- Buttons say what they do ("Save", "Add counterparty", "Log event", "View").
- Errors say what to fix ("Give a reason of at least 3 characters.").
- Dates as `12 Mar 2026`, money in USD as `$5.2M` (AED from Attio is converted by the Toolkit).
- Money inputs take the full amount in whole units, shown with comma separators as typed (`4,000,000`), never millions or decimals. The label names the currency ("Expected deal value (USD)"). Displays elsewhere stay short (`$4M`). Percentages may have decimals; months are whole numbers.

## 8. Starter CSS

Copy into another dashboard, then add the component rules above as needed. The full version lives in `app/styles.css`.

```css
:root {
  --navy: #000523;
  --sky: #c6e1ee;
  --sky-soft: #eaf3f8;
  --page: #f5f5f5;
  --surface: #ffffff;
  --ink: #1a1a1a;
  --line: #e4e4e7;
  --line-strong: #c9c9cf;
  --muted: #5e6670;
  --subtle: #707780;
  --alert: #8a1c1c;
  --font: "Inter Variable", system-ui, sans-serif;
  --radius-card: 16px;
  --radius: 10px;
  --radius-pill: 999px;
  --shadow: 0 1px 2px rgb(0 5 35 / 0.04), 0 8px 24px rgb(0 5 35 / 0.04);
}

* { box-sizing: border-box; }
html { font-family: var(--font); }
html, body { margin: 0; }
body { background: var(--page); color: var(--ink); font-size: 13px; line-height: 1.5; -webkit-font-smoothing: antialiased; }
button, input, select, textarea { font: inherit; }
a { color: var(--navy); text-underline-offset: 3px; }
:focus-visible { outline: 2px solid var(--navy); outline-offset: 2px; }

.page { max-width: 1440px; margin: 0 auto; padding: 24px 40px 16px; }
.page-title { margin: 0 0 16px; color: var(--navy); font-size: 32px; font-weight: 600; letter-spacing: -0.03em; line-height: 1.25; }
.section-title { margin: 0; color: var(--ink); font-size: 16px; font-weight: 600; }
.muted { color: var(--muted); }

.card { padding: 20px 24px; border: 0; border-radius: var(--radius-card); background: var(--surface); box-shadow: var(--shadow); }
.card + .card { margin-top: 12px; }

.button { display: inline-flex; align-items: center; justify-content: center; height: 36px; padding: 0 16px; border: 1px solid var(--navy); border-radius: var(--radius-pill); background: var(--navy); color: var(--surface); font-weight: 500; white-space: nowrap; cursor: pointer; }
.button--quiet { border-color: var(--line); background: var(--surface); color: var(--ink); }
.button--quiet:hover { background: var(--page); }
.button:disabled { opacity: 0.45; cursor: not-allowed; }

input, select, textarea { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); color: var(--ink); }
input, select { height: 36px; padding: 0 10px; }
input:focus-visible, select:focus-visible, textarea:focus-visible { border-color: var(--navy); outline: 2px solid var(--sky); outline-offset: 0; }

.badge { display: inline-block; padding: 2px 10px; border: 1px solid var(--sky); border-radius: 999px; background: var(--sky-soft); color: var(--navy); font-size: 12px; }

.table { width: 100%; border-collapse: separate; border-spacing: 0; overflow: hidden; border-radius: var(--radius); background: var(--surface); font-size: 13px; }
.table th, .table td { padding: 14px 12px; text-align: left; vertical-align: middle; }
.table thead th { padding-top: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--line); background: var(--surface); color: var(--muted); font-size: 12px; font-weight: 500; white-space: nowrap; }
.table tbody tr + tr td { border-top: 1px solid var(--line); }
.table .num { text-align: right; font-variant-numeric: tabular-nums; }
```
