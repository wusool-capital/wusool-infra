# 0003: Engagement letter terms and flow

Date: 7 Nov 2026 · Status: accepted (prototype)

## Context
PRD P4 asks for a terms dialog, then contract, proposal brief and NDA drafted by the existing skills, saved to Drive, and an email the deal owner sends. The PRD lists fee, minimum, retainer, exclusivity and term, and leaves the exact fields as an open question. The dialog would open from the quick-view drawer, which breaks the one-layer rule.

## Decision
- The terms form replaces the drawer content (Back returns), so the page keeps one layer. Agreed with Jules on 7 Nov 2026.
- Fields and defaults come from the skills that draft the documents:
  - Sell-side, structured process (`wusool-sellside-proposal` + `wusool-sellside-agreement`): 3% on buyers the client brings, 5% on buyers Wusool brings, $5,000/month retainer for up to 4 months credited against the fee, stake for sale, kickoff, target closing.
  - Sell-side, platform listing (`wusool-sellside-simplified-agreement`): higher of 8% or USD 10,000, fee trigger, listing channels, governing law, VAT, 12-month term. Default for deals under $3M.
  - Buy-side (`wusool-buyside-proposal` + `wusool-finder-fee-agreement`): Tier 1 at 3% with no retainer, Tier 2 at 5% with a $40,000 minimum and a $5,000/month retainer for up to 4 months.
  - Signatory: Jules (COO) by default, or Hugo (CEO).
- Client NDA: Jules's confidentiality agreement template (received 7 Nov 2026) goes in both sell-side packs. It is one-way (the company discloses, Wusool holds). The panel asks for what the template leaves blank: company legal name, jurisdiction, registration number, registered office, the company signatory, governing law (ADGM by default, as in the template) and the competitor sectors for clause 3.4 (default: the deal's sector). Send stays disabled until the legal details are filled. The buy-side pack has no NDA, since the template covers a company being sold. `wusool-nda` stays the NDA for buyers, used later in Mandates.
- The template file itself names a real client, so it is not stored in this repo.
- Exclusivity is dropped: no skill asks for it, and the simplified agreement is non-exclusive.
- Worked fee examples at the deal value are computed in code (`lib/engagement.ts`), as each skill requires.
- Documents are drafted from the default terms when the panel opens, so the usual path is 3 clicks: card, Draft engagement letter, Send. Changing a term disables Send until "Update documents".
- Terms are never stored on the deal, so no fee reaches the board, the list or any screen-shareable page (P5).

## Open
- No skill drafts the client NDA yet; the panel names it "Client NDA template". A `wusool-client-nda` skill should be built from the template.
- Production generation takes time; the "Update documents" step then becomes a real job with a progress state.
