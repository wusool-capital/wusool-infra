
/* ============================================================
   NARRATIVE
   ============================================================ */

const FLAGTEXT = {
  ebitda:{bad:["Margin sits below your peer set","Your operating profit margin of {v} is in the {p} percentile. In {s}, the peer median is around {m}. Buyers read a persistent margin gap as either pricing weakness or an overhead problem, and price it directly into the multiple."],
          good:["Margin is a genuine strength","At {v} you are in the {p} percentile of {s}. This is the single most quotable number in a sale process and it should lead your equity story."]},
  growth:{bad:["Growth has stalled relative to peers","Revenue moved {v} against a peer median near {m}. Two flat years is the most common reason a GCC SME sale process attracts only one bidder."],
          good:["Growth is ahead of the sector","At {v} you are in the {p} percentile. Sustained for another 12 months this alone supports a higher multiple than the sector average."]},
  revEmp:{bad:["Revenue per employee is low","You generate {c} {v}k per head against a peer median of {c} {m}k. A buyer will read this as either overstaffing or under-pricing, and will model headcount reduction into their synergy case rather than paying you for it."],
          good:["The business runs lean","{c} {v}k per head puts you in the {p} percentile. Operating leverage like this is what makes a bolt-on acquisition attractive to a larger group."]},
  conc:{bad:["Customer concentration is the biggest issue here","Your largest customer is {v} of revenue. Above roughly 25% most buyers either discount the price or push a large part of it into an earn-out tied to that customer staying. This is the highest-return thing on this page to fix."],
        good:["Revenue is well spread","At {v} from your largest customer you are in the {p} percentile. Removes the single most common reason GCC SME deals get restructured mid-process."]},
  gm:{bad:["Gross margin trails the sector","At {v} against a peer median of {m}, either your input costs or your pricing are out of line. Gross margin is easier to defend in diligence than operating profit, so a gap here is noticed early."],
      good:["Gross margin is strong","{v} puts you in the {p} percentile, which gives you room to absorb cost inflation without repricing."]},
  rent:{bad:["Premises cost is eating your margin","Rent and premises run at {v} of revenue against a peer median of {m}. In Dubai and Abu Dhabi this is the most common single cause of a sub-par margin, and lease terms transfer to a buyer, so it is priced."],
        good:["Premises cost is well controlled","At {v} of revenue you are in the {p} percentile. Worth confirming your remaining lease term, since buyers pay for security of tenure."]},
  recur:{bad:["Little of your revenue is contracted","{v} of revenue is contracted or repeat, against a peer median of {m}. Buyers pay a premium for visibility. Converting even part of your base onto annual agreements changes how the business is valued, not just how it trades."],
         good:["Revenue visibility is a strength","{v} contracted or repeat revenue puts you in the {p} percentile. This is the characteristic that most reliably pulls a valuation above the sector range."]}
};

const TECH_FLAG = {
  capEff:{bad:["Capital efficiency is behind the peer set","You generate {v} of revenue per dollar raised, against a peer median of {m} at {s}. Investors and acquirers read this as the cost of your growth. It is the metric that most often decides whether a round is priced up or flat."],
          good:["You are capital efficient for your stage","At {v} of revenue per dollar raised you are in the {p} percentile. This is the strongest argument you have for a premium multiple, and it widens your buyer set to include acquirers who will not fund a burn."]},
  revScale:{bad:["Revenue is light for the stage","At {v} you are in the {p} percentile of {s} companies. Raising the next round at this scale usually means selling the plan rather than the traction, which prices lower."],
            good:["Revenue is ahead of the stage","{v} puts you in the {p} percentile of {s} companies. You have the option of raising on traction rather than narrative."]},
  ebitda:{bad:["You are burning relative to peers","Your operating profit margin of {v} is in the {p} percentile for {s} at your revenue band. Acquirers will underwrite the path to breakeven, not the growth rate alone, and will discount for every quarter of runway they have to fund."],
          good:["Profitable ahead of the peer set","At {v} you are in the {p} percentile. Profitability at this stage is rare in GCC tech and it materially widens your buyer universe beyond venture-backed acquirers."]},
  recur:{bad:["Revenue is not sticky enough","{v} of revenue is recurring against a peer median of {m}. Buyers pay an ARR multiple for contracted revenue and an earnings multiple for everything else. That distinction is worth more than any single point of growth."],
         good:["Revenue quality is the strength here","{v} recurring puts you in the {p} percentile. This is what moves a valuation from an earnings multiple onto a revenue multiple."]},
  growth:{bad:["Growth has slowed against the peer set","Revenue moved {v} against a peer median near {m}. Two soft quarters is the most common reason a regional tech process attracts a single bidder rather than an auction."],
          good:["Growth is ahead of the peer set","At {v} you are in the {p} percentile. Held for another year this alone supports a premium to the regional range."]}
};
function fill(t,o){ return t.replace(/\{(\w)\}/g,(_,k)=>o[k]); }

function flagFor(key,d,secLabel){
  const t=(MODE==="tech"&&TECH_FLAG[key]) ? TECH_FLAG[key] : FLAGTEXT[key]; if(!t||d.pct==null) return null;
  const good=d.pct>=68, bad=d.pct<40;
  if(!good&&!bad) return null;
  const set=good?t.good:t.bad;
  const unit=d.meta.unit;
  const vs = unit==="k" ? Math.round(toDisp(d.value)) : pct(d.value);
  const med = unit==="k" ? Math.round(toDisp(d.anchors[2])) : pct(d.anchors[2]);
  return {
    tone: good?"good":(d.pct<25?"bad":"mid"),
    title: set[0],
    body: fill(set[1],{v:vs,p:ord(d.pct),m:med,s:secLabel.toLowerCase(),c:CUR()}),
    pct: d.pct
  };
}
