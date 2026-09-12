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
