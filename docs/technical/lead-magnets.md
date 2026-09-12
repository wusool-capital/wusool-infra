# Lead Magnets

Four free tools on wusoolcapital.com that give a visitor a business insight in
exchange for their contact details, which land as a lead in Attio. This
replaced an earlier setup on Vercel/Render/Tally that called an AI provider
directly from the browser with an exposed API key, and in one case could lose
a lead entirely if that call failed.

## The four tools

| Tool | What the visitor gets | Uses AI? |
| --- | --- | --- |
| Valuation | An estimated company valuation (DCF, trading comps, transaction comps, and a VC-rounds method) | Yes, but always falls back to a deterministic number if AI is unavailable |
| M&A Readiness | A 0–100 score on how ready the business is to be sold, plus recommendations | Yes — the only tool with no non-AI fallback (see below) |
| GCC SME Benchmark | How the business compares to similar peer companies | No — pure calculation, no AI at all |
| Buyer Network | Registers the visitor as a buyer looking for acquisitions | Yes, but only for an internal note; never blocks the application |

## How it's embedded

Each tool lives on its own page on the real site (e.g.
`wusoolcapital.com/valuation-tool`). That page carries one small script tag,
which builds an invisible frame right there on the page, loads the actual
tool inside it, and auto-resizes it to fit — visitors never see anything that
looks like an embed.

## How a submission is handled

Every submission goes through the same five-step sequence, in this order,
on purpose:

1. **Record the submission** — saved to a database table immediately, before
   anything else runs. This is the fix for the old lead-loss bug: the lead
   is durably safe from this point on, no matter what happens next.
2. **Respond to the visitor** — sent back before the AI/CRM work below, so a
   slow or failing AI call never makes anyone wait or see an error. What they
   see at this point is either an instant, non-AI calculated result
   (Benchmark, Valuation's final number), or — for Readiness only — the real
   AI result, because there's nothing else to show them; more on that below.
3. **AI work**, where the tool actually calls it.
4. **Write to the CRM (Attio)** — creates or updates a company record and a
   seller/buyer entry with everything computed above.
5. **Close out the record** — marks the whole thing done.

If step 3 or 4 fails, a background job automatically retries it later,
without anyone having to notice. Duplicate submissions (a double-click, a
retried request) are recognized and skipped rather than recorded twice.

## Why Readiness is the odd one out

For Benchmark and Valuation, there's always a real, defensible calculated
answer to show even if the AI call fails — so those two respond immediately
and let AI enrich the result in the background afterward. Readiness's entire
score, band, and recommendations come only from the model's judgment across
15 questions; there's no equivalent calculation to fall back to that wouldn't
be actively misleading. So Readiness waits for the real AI result before
responding at all — which means it's the one tool where an AI failure is
something the visitor can actually see, as a "please try again" message. The
lead itself is never lost either way, since it was already saved in step 1.

## Where things live in the CRM

The full detail (valuation numbers, benchmark scores, sector, everything)
lands in Attio directly, from this system. It reaches the CRM-sync
PostgreSQL database — the one described in [Architecture](architecture.md) —
only later, through the same nightly resync and webhook that keep the rest of
the CRM in sync; this system does not write the full record to that database
itself. See [Business rules](business-rules.md) for why Attio is always
written first.

## Testing and non-production traffic

Every non-production submission is flagged so it never mixes with real
leads, is invisible in the normal CRM view, and can never reach the
production database through the sync described above.
