
/* ============================================================
   RENDER
   ============================================================ */
function run(){
  if(!validate(3)) return;
  compute();
  go(4);
}

function unlock(){
  clearErrs();
  let ok=true;
  if(!$("g-name").value.trim()){ markErr("g-name","Enter your name."); ok=false; }
  if(!$("g-company").value.trim()){ markErr("g-company","Enter your company name."); ok=false; }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test($("g-email").value.trim())){ markErr("g-email","Enter a valid email."); ok=false; }
  if(!$("g-consent").checked){ $("e-consent").classList.add("show"); ok=false; }
  if(!ok) return;

  const btn=$("g-btn");
  btn.disabled=true; btn.innerHTML='<span class="spin"></span>Building your report';

  // Field names and shape match BenchmarkRequest (api/schemas.py) exactly —
  // the server scores its own copy from these raw figures; nothing computed
  // client-side (score, percentiles, impliedEv*) is sent, since the server
  // recomputes it as the source of truth for what lands in the CRM.
  // `sector` is separate from `peer_key`: tech mode's peer_key is the
  // funding stage, not the sector, so the CRM write needs the actual
  // sector sent too. SME mode's peer_key already is the sector.
  const payload = {
    submission_id: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`),
    mode: MODE,
    peer_key: MODE==="tech" ? S.inputs.stage : S.inputs.sector,
    sector: MODE==="tech" ? S.inputs.sector : null,
    company: $("g-company").value.trim(),
    name: $("g-name").value.trim() || null,
    email: $("g-email").value.trim().toLowerCase(),
    domain: null,
    geography: S.inputs.geo || null,
    consent: $("g-consent").checked,
    revenue: toUSD(S.inputs.revenue),
    prev_revenue: toUSD(S.inputs.prevRevenue),
    ebitda_reported: toUSD(S.inputs.ebitdaReported),
    owner_salary: toUSD(S.inputs.ownerSalary),
    salary_deducted: S.salaryDeducted,
    gross_margin_pct: S.inputs.grossMargin,
    headcount: S.inputs.headcount,
    rent_cost: toUSD(S.inputs.rentAed),
    capital_raised: toUSD(S.inputs.capitalRaised),
    top_customer_pct: S.inputs.topCustomerPct,
    recurring_pct: S.inputs.recurringPct,
    years_active: S.inputs.years,
    outlets: S.inputs.outlets,
    days_to_get_paid: S.inputs.dso
  };

  fetch("/benchmark",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})
    .then(r=>{ if(!r.ok) throw new Error("benchmark submit failed: "+r.status); })
    .catch(e=>console.warn("submit",e))
    .finally(()=>{ S.sent=true; render(); });
}

function render(){
  const {metrics,score}=S.results;

  // metric bands
  const order = MODE==="sme" ? ["ebitda","growth","revEmp","conc","gm","rent","recur"]
                             : ["growth","capEff","revScale","gm","recur","conc"];

  // Say plainly which lines were dropped for want of an input.
  const missing = order.filter(k=>!metrics[k] || metrics[k].pct==null)
                       .map(k=>METRICS()[k] ? METRICS()[k].label.toLowerCase() : null).filter(Boolean);
  const shownN = order.length - missing.length;
  $("cover").innerHTML = missing.length
    ? `<div class="cover"><strong>Based on ${shownN} of ${order.length} metrics.</strong> You did not give us enough to rank you on ${missing.length===1?missing[0]:missing.slice(0,-1).join(", ")+" or "+missing.slice(-1)}, so those lines are left out rather than guessed.</div>`
    : "";

  $("metrics").innerHTML = order.map(k=>{
    const d=metrics[k]; if(!d||d.pct==null) return "";
    const unit=d.meta.unit;
    const cu = (x)=> unit==="k" ? `${CUR()} ${fmt(toDisp(x))}k` : sh(x,unit);
    // Where lower is better, flip the printed scale so the band always reads
    // weakest on the left and strongest on the right.
    const disp = d.meta.hi ? d.anchors : d.anchors.slice().reverse();
    const q = quart(d.pct);
    const pos = Math.max(2,Math.min(98,d.pct));
    // Nudge the median label clear of the user's value when the two sit close.
    const medShift = Math.abs(pos-50) < 17 ? (pos <= 50 ? 58 : -58) : 0;
    return `<div class="metric">
      <div class="mhead">
        <span class="mname">${d.meta.label}</span>
        <span class="pill q${q}">${QLABEL[q]}</span>
      </div>
      <div class="band">
        <div class="track"></div>
        <div class="q" style="left:25%"></div><div class="q" style="left:50%"></div><div class="q" style="left:75%"></div>
        <span class="medlab" style="left:50%;transform:translateX(calc(-50% + ${medShift}px))">median ${cu(disp[2])}</span>
        <div class="mark" data-v="${cu(d.value)}" style="left:${pos}%"></div>
      </div>
      <div class="qlabels">${[1,2,3,4].map(i=>`<span>${QLABEL[i]}</span>`).join("")}</div>
    </div>`;
  }).join("");

  // flags: worst three, plus the single best
  const all=order.map(k=>flagFor(k,metrics[k],S.inputs.sectorLabel)).filter(Boolean);
  const bad=all.filter(f=>f.tone!=="good").sort((a,b)=>a.pct-b.pct).slice(0,3);
  const good=all.filter(f=>f.tone==="good").sort((a,b)=>b.pct-a.pct).slice(0,1);
  const show=[...bad,...good];
  $("flags").innerHTML = show.length ? show.map(f=>`
    <div class="flag"><div class="chip ${f.tone}"></div>
      <div><h4>${f.title}</h4><p>${f.body}</p></div></div>`).join("")
    : `<div class="flag"><div class="chip good"></div><div><h4>No outliers</h4>
        <p>Every metric sits inside the middle of your peer range. Nothing here would stop a process, and nothing here would drive a premium either. The next lever is scale.</p></div></div>`;

  // owner salary note
  if(S.inputs.ownerSalary>0){
    $("flags").insertAdjacentHTML("beforeend",`
      <div class="flag"><div class="chip mid"></div><div>
        <h4>Your salary has been added back</h4>
        <p>Operating profit is shown as ${CUR()} ${fmt(toDisp(S.results.adjEbitda))} including your ${CUR()} ${fmt(toDisp(S.inputs.ownerSalary))} add-back, so you are compared on the same basis as everyone else. A buyer will deduct a market salary for whoever replaces you, so the figure they underwrite will sit between the two.</p>
      </div></div>`);
  }

  $("lnk-val").href=CFG.valuationUrl;
  $("lnk-ready").href=CFG.readinessUrl;
  $("lnk-call").href=CFG.callUrl;

  $("meta").innerHTML = `<strong>Methodology.</strong> Peer ranges are built from published SaaS and venture benchmark sets, GCC listed technology disclosures, regional venture funding data, and Wusool's own technology mandates, adjusted for GCC scale. Percentiles are interpolated across five anchor points and adjusted for your size band. Ranges are indicative and are not a valuation. <a href="#" onclick="return false">Full methodology</a>.`;

  go(5);
}
