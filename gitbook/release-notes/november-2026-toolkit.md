# November 2026: Wusool Toolkit

Delivery period: 15 October – 17 November 2026.

## Bulk upload (new)

- **`/bulk-buyer` and `/bulk-seller`.** Upload a CSV or Excel file in Slack
  to add many profiles at once. Templates are provided.
- **Checked in full first.** If any row is invalid, nothing is added.
  Every problem is listed by line and column.
- **Confirm, then add.** A valid file shows a confirm step. The bot posts
  the result when the rows are added.
- **Safe to rerun.** Rows already in the CRM are skipped, never duplicated.

## A simpler deal pipeline

- **10 stages instead of 20.** Lead, Qualified, Engaged, Mandate signed,
  Preparation, Outreach, Non-binding offers, Due diligence, Closing, Closed.
- **A separate status.** Each deal is Active, On hold, Passed, or Lost. All
  124 existing deals were moved, and their stage history was kept.
- **Lead tools create deals at Lead.** New website leads start at Lead with
  status Active.
- **Approving a match** promotes a Lead deal to Qualified, and a deal it
  creates starts Active.

## Find-match and the pre-match popup

- **Ranks on what you typed.** The core business, such as "asset manager",
  is required. Modifiers such as "AI" only rank higher.
- **Your note wins.** "Anything specific about this search?" now outranks
  the stored buyer sector and geography.
- **No false matches.** Sellers with no sector data are no longer shown as
  matches. When no CRM seller fits, the bot says so and starts a Google Maps
  search for the real request.
- **Edit buyer from the popup.** When details are missing, "Before we
  match" offers **Edit buyer**. It opens the edit form with only the empty
  fields.
- **No quick-click mistakes.** **Run anyway** is hidden while the edit
  saves, and the buyer is checked again afterwards.
- **Longer meeting context.** Matching now reads each meeting summary
  whole. Each prompt holds far more meeting notes than before, and always
  includes the newest and oldest meetings.

## Seller discovery and enrichment

- **Up to five sellers per search.** A lead whose website doesn't match
  Google Maps is skipped, and the next lead takes its place.
- **Fewer false duplicates.** A shared generic word such as "Intelligence"
  or "GmbH" no longer matches a lead to an existing company. A similar
  lead is skipped and counted.
- **LinkedIn scan.** After a proposal, the bot replies in its thread with
  the organization's recent LinkedIn posts. The company page can also fill
  missing company details. People are not scraped.
- **`/enrich-buyer`** asks for the organization first, then the vertical,
  like `/edit-buyer`.
- **Saved proposals show who saved them.** The button becomes "ADDED by".

## Slack polish

- **No more Slack form errors.** Whole numbers such as "12.0" are sent in
  the form Slack accepts. A number that can't be fixed is left blank.
- **Emptying a field.** Clearing a field in Slack now clears it in Attio.
- **Smaller cards.** Links in bot messages no longer expand into previews.
- **Reasoning that reads cleanly.** If the AI leaks stray markup into a
  text field, the step retries once instead of saving it.
- **Checked AI answers.** Every AI step now validates its answer before
  use. Meeting summaries retry once if they break the length rules.
