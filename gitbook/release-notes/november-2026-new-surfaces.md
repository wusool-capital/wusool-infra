# November 2026: Engine and MCP

Delivery period: 15 October – 17 November 2026.

## The Wusool Engine (new)

The Engine is a web app built by the advisors' team. It now reads and
writes live Wusool data.

- **Live at `engine.wusoolcapital.com`.** Staff sign in with a one-time
  code sent to their work email. A separate copy for testing runs on dev.
- **Buyers and Sellers on live data.** Both pages filter, search, and page
  through the real CRM. Edits follow the same rules as Slack: Attio first,
  then the database.
- **Range filters with a slider.** Check size, minimum EBITDA, revenue, and
  EBITDA use a two-handle slider with named steps such as $200K, $5M, and
  $1B+. This stops 200K and 200M being mixed up.
- **Drawers show the full record.** Extra fields such as investment
  strategy appear, and so do contact emails. Web addresses are clickable.
- **Edit forms cover everything Slack covers.** Each form has two sections,
  one for the buyer or seller and one for the company. The company sector
  and HQ country are editable. A new buyer can pick any allowed vertical.
- **Add a seller.** A seller can be added from the Engine.
- **Emptying a field works.** Clearing a field now clears it in Attio too.
- **A seller shows its company's sector** when it has none of its own.
- **Pages without data stay greyed out** until their turn. Only Buyers,
  Sellers, and the links out are active.

Fixes during the rollout: editing only a seller's extra fields, such as the
company description, now saves.

## Wusool MCP for Claude (new)

- **Connect once.** Advisors sign in with Slack. Only active members of the
  Wusool workspace can connect. Someone who leaves loses access.
- **Find.** Claude can list buyers and sellers by vertical, region, check
  size, and status, and read a full record. It can run the `/check-buyer`
  check and show each field's allowed values.
- **Add and edit.** Changes save straight away, Attio first. A company that
  already holds the role comes back as the existing record.
- **Bulk import.** Claude checks a list of up to 1,000 rows and shows a
  preview. Nothing is saved until the advisor confirms. If any row is
  invalid, the whole list is rejected and each problem is named.
- **Everything is attributed.** Every change is recorded against the person
  who made it. Every tool call leaves a history entry, without its contents.
- **Benchmark data in Claude.** The GCC SME Benchmark's peer anchors,
  revenue bands, and metric weights now live in the database. Advisors can
  read and edit them from Claude, and each row shows who last changed it.
  Edits apply to the public benchmark straight away.
