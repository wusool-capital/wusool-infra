# October 2026: Website lead tools and reports

Delivery period: 15 September – 10 October 2026.

## Gated reports (new)

A new way to turn Wusool's research into leads.

- **Reports on the website.** Reports are published at
  `wusoolcapital.com/reports`, each with its own page and card.
- **Gated preview.** New readers see the first page, then enter their name,
  email, and an optional organization.
- **Email confirmation.** Readers confirm with a 6-digit code before the
  report opens, so only genuine contacts become leads.
- **Download PDF.** Unlocked readers can download the full report as an A4
  PDF. On larger screens, A4 reports display page by page, like a PDF
  viewer.
- **Leads in Attio.** Every confirmed reader is added to Attio as a contact,
  plus an organization when they give one. Every report each person reads is
  recorded.
- **Returning readers** skip the form.
- **Complex reports work too.** Reports built with JavaScript, such as the
  "Buyouts in the GCC" playbook, are drawn once on the server. Readers get a
  fast static page that shrinks to fit on phones.
- **Old links keep working.** Reports moved from `/insights` redirect to
  their new pages.
- Reports hide the site's navigation and footer, so the reader stays on the
  report.

## The Wusool Reports Studio (new)

The team now publishes without Webflow or a developer.

- **Write reports and articles** in the Studio, either by pasting exported
  HTML or in a rich text editor.
- **Publishing updates the website automatically.** A report's card appears
  on `/reports`, and an Insights article appears on `/insights`.
- **Pin to top of /reports** features a report, and **Pin to home page
  banner** shows "Just released: … Get the playbook →" across the home page.
  Pins always stay in step between the Studio and the site.
- **End-of-page button.** Each report can end with a custom call to action.
- **Safe for existing content.** Hand-written Webflow articles are never
  overwritten, and article content is cleaned of unsafe code.
- Republishing a hidden report brings its card back, and the featured slot
  is never left empty.

## Get Started completed

The site's main "Get Started" form moved onto the platform on 14 September.
This period finished it:

- It sends the same confirmation and team emails as the other tools.
- It is tracked as its own lead source in Attio.
- Its overlay no longer flashes on the page before the button is clicked.

## Valuation and Readiness redesign

- **New design.** Both tools have Inter type, a warm off-white page, and
  card-style questions. Readiness scores use shades of blue.
- **Faster valuations.** Valuation shows a preliminary result after its
  loading screen, then refines it in place: Preliminary, then Done.
- **The AI analyst's judgement counts.** When a business is a poor fit for
  its sector tag, Valuation uses the analyst's growth assumptions, discounts,
  and comparables. The page says when it does.
- **Attio matches what the visitor saw.** The valuation saved in Attio uses
  the analyst-refined figures, recorded once the analysis finishes.
- **Better models.** A new Childcare & Early Education sector, more
  realistic DCF margins, an editable illiquidity discount, and warnings for
  implausible results.
- Readiness's Back button on the first question now works.

## Every lead in the CRM, properly

- **Two emails per lead.** Visitors get a branded confirmation with a Book a
  Call link, and the team gets a notice linking to the Attio record.
- **Lead source.** Each organization records which tool it came through, so
  "which leads came from the Valuation tool?" can finally be answered. Report
  readers have their own source, "Insights & Reports".
- **Answers on the CRM activity.** Each submission's answers are copied onto
  its Attio activity, so advisors can see exactly what a visitor entered.
- **Seller sector.** Valuation, Benchmark, and Readiness record the seller's
  sector on its own profile.
- **One buyer profile per sector.** Buyer Network creates one buyer profile
  for each sector ticked, so each can be matched separately.
- **Retries never block.** Visitors can resubmit any tool as often as they
  like; every attempt is recorded and never merged or lost. A network retry
  never sends a second email.
- **Unlock on booking.** Valuation and Readiness unlock the full report a few
  seconds after the booking button is clicked.
- An email that fails to send raises an alert.
