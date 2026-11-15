# 0005: Merge Mandates into Pipeline

Date: 7 Nov 2026 · Status: accepted

## Context
Mandates was the Pipeline filtered to signed deals, plus three counts (buyers in play, NDAs, offers) and a link to the Deal view. Two tabs showed the same deals, and Jules asked whether to merge them.

## Decision
- One Pipeline tab; Mandates leaves the nav (13 tabs).
- A card opens the quick-view drawer for fast edits (stage, owner, value, next step, blurb, engagement letter). "Open deal" in its header goes to the Deal view at `/deals/<id>`.
- The Deal view has a "< Pipeline" link that returns to the board or list it came from, with its filters (passed in the link's state).
- The Pipeline list shows In play, NDAs and Offers per deal.
- `/mandates` redirects to the Pipeline list; `/mandates/<id>` to `/deals/<id>`, keeping the query.

## Consequences
- The Deal view opens for any stage; before Mandate signed its Buyers and Offers tabs are simply empty.
- The `mandates` component folder keeps its name (it holds the Deal view parts); its README says so.
