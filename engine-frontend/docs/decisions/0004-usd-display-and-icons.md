# 0004: USD display, filter Apply, and the icon library

Date: 7 Nov 2026 · Status: accepted

## Context
Jules reviewed the Buyers and Sellers pages: amounts showed in AED, filters fired on every change, and the "..." menu was a text button.

## Decision
- **Money in USD only.** Attio stores check size, EBITDA floor, revenue and EBITDA in AED. The Toolkit converts at the 3.6725 peg and returns USD, so the front-end has one currency and no conversion code. Demo data is already in USD.
- **Filters apply on Apply.** Each filter is a button with a popover holding a draft; the URL (and, once live, the Toolkit query) changes only on Apply. One query per Apply instead of one per tick.
- **Ranges as Min and Max in $M**, not sliders: amounts span $0.5M to $100M+ and typed values are exact.
- **Phosphor icons** (`@phosphor-icons/react`), one family, no hand-drawn SVG. The select chevron is Phosphor's CaretDown path as a CSS background, the only place an icon is inlined.

## Consequences
- The Toolkit API contract for buyer and seller roles carries USD fields (`*_usd`).
- Shared pieces: `ui/filter-bar.tsx` (filter buttons), `lib/filters.ts` (URL format), `ui/actions-menu.tsx`, `ui/record-parts.tsx` (drawer header, emails log).
