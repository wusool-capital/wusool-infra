"""Benchmark report copy — generated, do not hand-edit.

The paragraph a visitor reads for each metric they rank well or badly on,
extracted verbatim from `FLAGTEXT`/`TECH_FLAG` in `wusool-benchmark.html`.
This is client-facing prose written by the business; it is quoted, never
paraphrased.

Placeholders, filled by `flag_for` in `benchmark_narrative.py`:
  {v} the visitor's own value   {p} their percentile, as an ordinal
  {m} the peer median           {s} the peer-set label, lowercased
  {c} the display currency
"""

from app.modules.lead_magnets.domain.benchmark_narrative import FlagCopy

SME_FLAG_COPY: dict[str, FlagCopy] = {
    "ebitda": FlagCopy(
        bad_title="Margin sits below your peer set",
        bad_body="Your operating profit margin of {v} is in the {p} percentile. In {s}, the peer median is around {m}. Buyers read a persistent margin gap as either pricing weakness or an overhead problem, and price it directly into the multiple.",
        good_title="Margin is a genuine strength",
        good_body="At {v} you are in the {p} percentile of {s}. This is the single most quotable number in a sale process and it should lead your equity story.",
    ),
    "growth": FlagCopy(
        bad_title="Growth has stalled relative to peers",
        bad_body="Revenue moved {v} against a peer median near {m}. Two flat years is the most common reason a GCC SME sale process attracts only one bidder.",
        good_title="Growth is ahead of the sector",
        good_body="At {v} you are in the {p} percentile. Sustained for another 12 months this alone supports a higher multiple than the sector average.",
    ),
    "revEmp": FlagCopy(
        bad_title="Revenue per employee is low",
        bad_body="You generate {c} {v}k per head against a peer median of {c} {m}k. A buyer will read this as either overstaffing or under-pricing, and will model headcount reduction into their synergy case rather than paying you for it.",
        good_title="The business runs lean",
        good_body="{c} {v}k per head puts you in the {p} percentile. Operating leverage like this is what makes a bolt-on acquisition attractive to a larger group.",
    ),
    "conc": FlagCopy(
        bad_title="Customer concentration is the biggest issue here",
        bad_body="Your largest customer is {v} of revenue. Above roughly 25% most buyers either discount the price or push a large part of it into an earn-out tied to that customer staying. This is the highest-return thing on this page to fix.",
        good_title="Revenue is well spread",
        good_body="At {v} from your largest customer you are in the {p} percentile. Removes the single most common reason GCC SME deals get restructured mid-process.",
    ),
    "gm": FlagCopy(
        bad_title="Gross margin trails the sector",
        bad_body="At {v} against a peer median of {m}, either your input costs or your pricing are out of line. Gross margin is easier to defend in diligence than operating profit, so a gap here is noticed early.",
        good_title="Gross margin is strong",
        good_body="{v} puts you in the {p} percentile, which gives you room to absorb cost inflation without repricing.",
    ),
    "rent": FlagCopy(
        bad_title="Premises cost is eating your margin",
        bad_body="Rent and premises run at {v} of revenue against a peer median of {m}. In Dubai and Abu Dhabi this is the most common single cause of a sub-par margin, and lease terms transfer to a buyer, so it is priced.",
        good_title="Premises cost is well controlled",
        good_body="At {v} of revenue you are in the {p} percentile. Worth confirming your remaining lease term, since buyers pay for security of tenure.",
    ),
    "recur": FlagCopy(
        bad_title="Little of your revenue is contracted",
        bad_body="{v} of revenue is contracted or repeat, against a peer median of {m}. Buyers pay a premium for visibility. Converting even part of your base onto annual agreements changes how the business is valued, not just how it trades.",
        good_title="Revenue visibility is a strength",
        good_body="{v} contracted or repeat revenue puts you in the {p} percentile. This is the characteristic that most reliably pulls a valuation above the sector range.",
    ),
}

TECH_FLAG_COPY: dict[str, FlagCopy] = {
    "capEff": FlagCopy(
        bad_title="Capital efficiency is behind the peer set",
        bad_body="You generate {v} of revenue per dollar raised, against a peer median of {m} at {s}. Investors and acquirers read this as the cost of your growth. It is the metric that most often decides whether a round is priced up or flat.",
        good_title="You are capital efficient for your stage",
        good_body="At {v} of revenue per dollar raised you are in the {p} percentile. This is the strongest argument you have for a premium multiple, and it widens your buyer set to include acquirers who will not fund a burn.",
    ),
    "revScale": FlagCopy(
        bad_title="Revenue is light for the stage",
        bad_body="At {v} you are in the {p} percentile of {s} companies. Raising the next round at this scale usually means selling the plan rather than the traction, which prices lower.",
        good_title="Revenue is ahead of the stage",
        good_body="{v} puts you in the {p} percentile of {s} companies. You have the option of raising on traction rather than narrative.",
    ),
    "ebitda": FlagCopy(
        bad_title="You are burning relative to peers",
        bad_body="Your operating profit margin of {v} is in the {p} percentile for {s} at your revenue band. Acquirers will underwrite the path to breakeven, not the growth rate alone, and will discount for every quarter of runway they have to fund.",
        good_title="Profitable ahead of the peer set",
        good_body="At {v} you are in the {p} percentile. Profitability at this stage is rare in GCC tech and it materially widens your buyer universe beyond venture-backed acquirers.",
    ),
    "recur": FlagCopy(
        bad_title="Revenue is not sticky enough",
        bad_body="{v} of revenue is recurring against a peer median of {m}. Buyers pay an ARR multiple for contracted revenue and an earnings multiple for everything else. That distinction is worth more than any single point of growth.",
        good_title="Revenue quality is the strength here",
        good_body="{v} recurring puts you in the {p} percentile. This is what moves a valuation from an earnings multiple onto a revenue multiple.",
    ),
    "growth": FlagCopy(
        bad_title="Growth has slowed against the peer set",
        bad_body="Revenue moved {v} against a peer median near {m}. Two soft quarters is the most common reason a regional tech process attracts a single bidder rather than an auction.",
        good_title="Growth is ahead of the peer set",
        good_body="At {v} you are in the {p} percentile. Held for another year this alone supports a premium to the regional range.",
    ),
}
