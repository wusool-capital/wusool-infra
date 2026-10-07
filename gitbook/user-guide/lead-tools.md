# Website lead tools

Wusool Capital provides four public tools through its website. Visitors get a
report or submit an acquisition profile; their contact and company details
are recorded for follow-up in Attio.

| Tool | What the visitor receives |
| --- | --- |
| **Valuation** | Estimated company valuation using several methods |
| **M&A Readiness** | A 0–100 readiness score and recommendations from 15 questions |
| **GCC SME Benchmark** | A comparison with relevant peer companies |
| **Buyer Network** | Registration as a buyer seeking acquisitions |

## Publish a gated report

Gated reports are written in the Wusool Reports Studio (Sanity), not in
Webflow.

1. Create a **Report**, fill in the title, then click **Generate** for the
   slug or type your own.
2. Pick **Write with**. Paste the exported report HTML, and readers see page
   one. Or write it in the rich text editor, and readers see about the first
   quarter.
3. Optionally fill in the excerpt, cover image, primary silo, date, and the
   end-of-page button (text and link).
4. Tick **Pin to top of /reports** to make it the featured card. This
   unpins the card that is currently featured.
5. Publish.

**Expected result:** shortly after publishing, the report has a card on
`wusoolcapital.com/reports` and its own page there. Readers see the first
page (or first quarter of a rich text report), then a short form; the organization field is optional. Completing it
opens the full report and its **Download PDF** button. The reader appears in
Attio as a person, plus an organization when they gave one. Returning
readers skip the form.

Changing a published report's slug moves it to the new URL, and the old URL
stops working. Unpublishing it in the Studio removes the card.

## Publish an Insights article

Insights articles can also be written in the Wusool Reports Studio.

1. Create an **Insights article** and fill in the title, slug, content type
   and excerpt.
2. Pick **Write with**: the rich text editor, or pasted HTML. Then write the
   body, and optionally the key takeaways and FAQ.
3. Optionally fill in the cover image, author, silo, SEO fields and the
   end-of-page button. Blank SEO fields use the title and excerpt.
4. Publish.

**Expected result:** the article appears on `wusoolcapital.com/insights`
shortly after publishing. It isn't pinned; pin articles in Webflow. An
existing hand-written article with the same slug is left untouched.

## Use a tool

1. Open the relevant tool page on the Wusool Capital website.
2. Enter accurate company and contact information and complete the required
   financial, questionnaire, or acquisition-preference fields.
3. Review the consent text and submit once.
4. Read the result on screen and follow any offered contact or booking action.

**Expected result:** Valuation shows a calculated report, Readiness returns a
score and advice, Benchmark shows peer comparisons, and Buyer Network confirms
the application. The submission is recorded before downstream CRM processing
so a later integration failure does not discard the lead.

## Example: complete a valuation

An owner of **Example Manufacturing** enters current revenue, cash, debt, and
contact details, accepts the consent statement, and submits the Valuation tool.

**Expected result:** the page displays a low, midpoint, and high estimate with
the methods used. A corresponding organization and seller context appear in
Attio after processing. The figures are decision-support estimates, not a
formal valuation.

If the page reports a validation error, correct the highlighted field and
submit again. If a result already appeared, do not submit a second time merely
because Attio is still processing the record.

## Find the submission in Attio

Search using the submitted email, company name, or domain. Valuation,
Readiness, and Benchmark information belongs with seller context; Buyer
Network information belongs with buyer context. CRM processing can finish
shortly after the browser result, so allow a brief delay. Non-production
submissions are marked as test data and should not appear in normal production
lead views.

## Understand the result

- **Valuation** blends deterministic methods. AI and public search may enrich
  the analysis, but a calculated valuation remains available without them.
- **Readiness** depends on AI judgment and has no substitute score. A service
  failure can show a retry message even though the lead was retained.
- **Benchmark** is calculated from a peer dataset without an AI model.
- **Buyer Network** accepts an application without waiting for its optional
  internal AI qualification note.

These are indicative decision-support outputs, not a formal valuation,
transaction recommendation, financing offer, or promise of contact.

## If a tool does not complete

- Preserve the tool name, entered information, time, and exact error before
  refreshing.
- Retry once after checking required fields and connectivity. Repeated
  submissions may be recognized as duplicates.
- If a result appeared but Attio remains empty after a reasonable delay,
  contact support through an approved private channel. Include the tool name,
  time, company domain, and submitted email.
