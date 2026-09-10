
/* ============================================================
   PERCENTILE ENGINE
   ============================================================ */
const ANCHORS=[10,25,50,75,90];

// piecewise-linear percentile rank against 5 anchor points, with tail extrapolation
function rank(v, a){
  if(v==null||!a) return null;
  if(v<=a[0]){ const step=(a[1]-a[0])||1; return Math.max(1, 10 - ((a[0]-v)/step)*15); }
  if(v>=a[4]){ const step=(a[4]-a[3])||1; return Math.min(99, 90 + ((v-a[4])/step)*15); }
  for(let i=0;i<4;i++){
    if(v>=a[i]&&v<=a[i+1]){
      const span=(a[i+1]-a[i])||1;
      return ANCHORS[i] + ((v-a[i])/span)*(ANCHORS[i+1]-ANCHORS[i]);
    }
  }
  return 50;
}

function bandFor(rev){
  const bs=DATA.bands;
  for(const b of bs) if(b.max===null||rev<b.max) return b;
  return bs[bs.length-1];
}

function adjust(key, arr, band){
  if(MODE!=="sme") return arr.slice();          // stage IS the cut; no band adjustment
  if(key==="ebitda") return arr.map(x=>x+band.ebitdaAdj);
  if(key==="revEmp") return arr.map(x=>x*band.revEmpMult);
  if(key==="rent")   return arr.map(x=>x*(band.rentMult||1));
  return arr.slice();
}

// which quartile a percentile falls in
function quart(p){ return p<25?1 : p<50?2 : p<75?3 : 4; }
const QLABEL=["","Bottom 25%","Below Average","Above Average","Top 25%"];

function compute(){
  const tech=MODE==="tech";
  // All money is converted to USD first, in both modes.
  const rev=toCalc(num($("rev").value)), prev=toCalc(num($("prev").value));
  const rawEbitda=toCalc(num($("ebitda").value));
  const salary=S.salaryDeducted ? (toCalc(num($("salary").value))||0) : 0;
  const adjEbitda = rawEbitda==null ? null : rawEbitda+salary;
  const staff=num($("staff").value);
  const rentUsd=toCalc(num($("rent").value));
  const raised=num($("raised").value);   // tech only, always USD

  const cut = tech ? DATA.stages[$("stage").value] : DATA.sectors[$("sector").value];
  const cutLbl = tech ? cut.label : cut.label;
  const band = tech ? {id:$("stage").value,label:cut.label} : bandFor(rev);

  const v = {
    ebitda:  (rev&&adjEbitda!=null)? (adjEbitda/rev)*100 : null,
    gm:      num($("gm").value),
    growth:  (prev&&prev>0)? ((rev-prev)/prev)*100 : null,
    revEmp:  (rev&&staff)? (rev/staff)/1000 : null,
    rent:    (!tech&&rentUsd!=null&&rev)? (rentUsd/rev)*100 : null,
    conc:    num($("conc").value),
    recur:   num($("recur").value),
    revScale: tech? rev : null,
    capEff:  (tech&&raised&&raised>0)? rev/raised : null
  };

  const out={}; let wSum=0,pSum=0;
  for(const [k,meta] of Object.entries(METRICS())){
    if(v[k]==null || !cut.m[k]){ out[k]={value:null,pct:null,anchors:null,meta}; continue; }
    const anchors=adjust(k, cut.m[k], band);
    let p=rank(v[k],anchors);
    if(!meta.hi) p=100-p;
    p=Math.max(1,Math.min(99,p));
    out[k]={value:v[k],pct:p,anchors,meta,q:quart(p)};
    wSum+=meta.w; pSum+=p*meta.w;
  }
  const score=wSum? Math.round(pSum/wSum) : 50;
  const covered=Object.values(out).filter(d=>d.pct!=null).length;

  // startup mode: implied enterprise value from observed forward revenue multiples
  let val=null;
  if(tech && cut.m.fwdMult && rev){
    const fwd = (prev&&prev>0&&rev>prev) ? rev*(rev/prev) : rev*1.5;   // next-year revenue proxy
    val = { low: fwd*cut.m.fwdMult[1], mid: fwd*cut.m.fwdMult[2], high: fwd*cut.m.fwdMult[3],
            fwdRev: fwd, mults:[cut.m.fwdMult[1],cut.m.fwdMult[2],cut.m.fwdMult[3]] };
  }

  S.inputs={mode:MODE, modeLabel: tech?"Startup":"SME",
    sector:$("sector").value, sectorLabel:$("sector").value,
    stage: tech?$("stage").value:null, stageLabel: tech?cut.label:null,
    cutLabel:cutLbl, geo:$("geo").value, years:num($("years").value),
    revenue:rev, prevRevenue:prev, ebitdaReported:rawEbitda, ownerSalary:salary,
    ebitdaAdjusted:adjEbitda, grossMargin:v.gm, rentAed: tech?null:rentUsd,
    headcount:staff, capitalRaised: tech?raised:null,
    outlets: shown($("outlets")) ? num($("outlets").value) : null,
    topCustomerPct:v.conc, recurringPct:v.recur,
    dso: shown($("dso")) ? num($("dso").value) : null,
    band:band.id, bandLabel:band.label, sampleSize:cut.n,
    currency:"USD", entryCurrency:CUR(), fxRateAedPerUsd:FX,
    metricsCovered:covered, metricsTotal:Object.keys(METRICS()).length,
    dataCompleteness:Math.round(wSum)};
  if(!tech) S.inputs.sectorLabel = DATA.sectors[$("sector").value].label;
  S.results={metrics:out,score,band,sec:cut,adjEbitda,val,covered,wSum};
  return S.results;
}
