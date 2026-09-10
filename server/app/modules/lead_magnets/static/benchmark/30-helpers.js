
/* ============================================================
   STATE + HELPERS
   ============================================================ */
let MODE = "sme";
let DISP = "AED";                 // entry + display currency (SME mode only)
const FX = 3.6725;                // AED per USD, pegged
let S = { salaryDeducted:false, inputs:{}, results:null, sent:false };
// The engine computes in USD in both modes. The toggle governs entry and
// display only, so a founder can still work in AED throughout.
// entry currency -> USD
const toCalc = v => v==null ? null : (MODE==="tech" ? v : (DISP==="AED" ? v/FX : v));
// USD -> display currency
const toDisp = v => v==null ? null : (MODE==="tech" ? v : (DISP==="AED" ? v*FX : v));
// USD -> the Attio write. Already USD, so this only rounds.
const toUSD  = v => v==null ? null : Math.round(v);
const METRICS = () => MODE==="sme" ? DATA.metrics : DATA.techMetrics;
const CUT = () => MODE==="sme" ? DATA.sectors[$("sector").value] : DATA.stages[$("stage").value];
const $ = id => document.getElementById(id);
const num = v => { const n = parseFloat(String(v).replace(/[^0-9.\-]/g,"")); return isNaN(n)?null:n; };
const fmt = n => n==null ? "n/a" : Math.round(n).toLocaleString("en-US");
const pct = n => n==null ? "n/a" : (Math.round(n*10)/10) + "%";
const fmtM = n => n>=1e9 ? (n/1e9).toFixed(1)+"bn" : n>=1e6 ? (n/1e6).toFixed(1)+"m" : Math.round(n/1e3)+"k";
const sh = (n,u) => u==="%" ? (Math.round(n*10)/10)+"%"
                  : u==="x" ? (Math.round(n*100)/100)+"x"
                  : u==="$" ? "$"+fmtM(n)
                  : u==="k" ? fmt(n)+"k" : fmt(n);
const ord = p => { const r=Math.round(p); const s=["th","st","nd","rd"], v=r%100; return r+(s[(v-20)%10]||s[v]||s[0]); };

function fillSectors(){
  const sel=$("sector");
  sel.innerHTML='<option value="">Select</option>';
  if(MODE==="sme"){
    Object.entries(DATA.sectors).sort((a,b)=>a[1].label.localeCompare(b[1].label))
      .forEach(([k,v])=>{ const o=document.createElement("option"); o.value=k; o.textContent=v.label; sel.appendChild(o); });
  } else {
    DATA.techSectorList.forEach(s=>{ const o=document.createElement("option"); o.value=s; o.textContent=s; sel.appendChild(o); });
  }
}
function CUR(){ return MODE==="tech" ? "USD" : DISP; }

const MONEY = ["rev","prev","ebitda","salary","rent"];
const PH = {
  AED:{rev:"5,000,000", prev:"4,400,000", ebitda:"700,000", salary:"360,000", rent:"750,000"},
  USD:{rev:"1,360,000", prev:"1,200,000", ebitda:"190,000", salary:"98,000",  rent:"204,000"}
};
function applyPH(){ const m=PH[CUR()]||PH.AED; MONEY.forEach(id=>{ if(m[id]) $(id).placeholder=m[id]; }); }

function convertFields(f){
  MONEY.forEach(id=>{
    const el=$(id); if(!el.value.trim()) return;
    const v=num(el.value); if(v==null) return;
    el.value = Math.round(v*f).toLocaleString("en-US");
  });
}
function setCur(c){
  if(MODE==="tech" || c===DISP) return;
  convertFields((c==="USD") ? 1/FX : FX);         // convert what is already typed
  DISP=c;
  $("cur-AED").classList.toggle("on", c==="AED");
  $("cur-USD").classList.toggle("on", c==="USD");
  document.querySelectorAll(".cur").forEach(e=>e.textContent=CUR());
  applyPH();
}
function setMode(m){
  // Startup mode is USD-native. Carry any figures already typed across at the peg
  // rather than silently reinterpreting the units.
  if(typeof MONEY!=="undefined"){
    if(m==="tech" && MODE!=="tech" && DISP==="AED") convertFields(1/FX);
    if(m!=="tech" && MODE==="tech" && DISP==="AED") convertFields(FX);
  }
  MODE=m;
  $("m-sme").classList.toggle("on",m==="sme");
  $("m-tech").classList.toggle("on",m==="tech");
  fillSectors();
  const t = m==="tech";
  $("stagewrap").classList.toggle("hide",!t);
  $("raisedwrap").classList.toggle("hide",!t);
  $("rentwrap").classList.toggle("hide",t);
  $("curtog").classList.toggle("hide",t);
  applySector();
  document.querySelectorAll(".cur").forEach(e=>e.textContent=CUR());
  applyPH();
  $("pfx-raised").textContent="USD";
  $("lbl-sector").textContent = "Sector";
  $("lbl-rev").textContent    = t ? "Revenue, last full year" : "Revenue, last full year";
  $("lbl-prev").textContent   = t ? "Revenue, prior year"     : "Revenue, year before";
  $("lbl-recur").textContent  = t ? "Recurring revenue share (%)" : "Contracted or repeat revenue (%)";
  $("s2h").textContent        = t ? "Last twelve months"      : "Last financial year";
}

// Step 3 fields depend on the chosen sector, and only ever show in SME mode.
function applySector(){
  const s = (MODE==="sme") ? DATA.sectors[$("sector").value] : null;
  $("outwrap").classList.toggle("hide", !s || !s.multiSite);
  $("dsowrap").classList.toggle("hide", !s || !s.b2b);
}

setMode("sme");

// thousands separators on money fields
["rev","prev","ebitda","salary","rent","raised"].forEach(id=>{
  $(id).addEventListener("input",e=>{
    const raw=e.target.value.replace(/[^0-9\-]/g,"");
    e.target.value = raw==="" ? "" : Number(raw).toLocaleString("en-US");
  });
});

// adapt step 3 to the sector
$("sector").addEventListener("change", applySector);

function setSal(deducted){
  clearErrs();
  S.salaryDeducted=deducted;
  $("sal-y").classList.toggle("on",deducted);
  $("sal-n").classList.toggle("on",!deducted);
  $("salwrap").classList.toggle("hide",deducted);
}

function fieldWrap(el){
  let p=el.parentNode;
  if(p.classList.contains("prefix")||p.classList.contains("suffix")) p=p.parentNode;
  return p;
}
function shown(el){ return !!(el && el.offsetParent !== null); }
function markErr(id,msg){
  const el=$(id); el.classList.add("err");
  const wrap=fieldWrap(el);
  let e=wrap.querySelector(".errtext");
  if(!e){ e=document.createElement("div"); e.className="errtext"; wrap.appendChild(e); }
  if(msg) e.textContent=msg;
  e.classList.add("show");
  return false;
}
function clearErrs(){
  document.querySelectorAll(".err").forEach(e=>e.classList.remove("err"));
  document.querySelectorAll(".errtext.show").forEach(e=>e.classList.remove("show"));
}
function clearConsentErr(){
  if($("g-consent").checked) $("e-consent").classList.remove("show");
}
// Only the fields the engine cannot run without are required. Anything left
// blank is dropped from the benchmark rather than defaulted to zero.
function requiredFor(step){
  const tech = MODE==="tech";
  if(step===1) return ["sector","geo"].concat(tech?["stage"]:[]);
  if(step===2) return ["rev","ebitda","staff"].concat(S.salaryDeducted?["salary"]:[]);
  if(step===3) return [];
  return [];
}
function validate(step){
  clearErrs();
  let ok=true;
  for(const id of requiredFor(step)){
    const el=$(id);
    if(!shown(el)) continue;
    const v=el.value.trim();
    if(v===""){ markErr(id,"This field is required."); ok=false; continue; }
    if(el.tagName!=="SELECT" && num(v)===null){ markErr(id,"Enter a number."); ok=false; }
  }
  const pctFields=["gm","conc","recur"];
  for(const id of pctFields){
    const el=$(id); if(!shown(el)||el.value.trim()==="") continue;
    const n=num(el.value);
    // n===null (non-numeric input) must fail explicitly — n<0||n>100 alone
    // lets it through silently, since JS coerces null<0 and null>100 to false.
    if(n===null||n<0||n>100){ markErr(id,"Enter a value between 0 and 100."); ok=false; }
  }
  return ok;
}
function go(step){
  if(step===2 && !validate(1)) return;
  if(step===3 && !validate(2)) return;
  ["s1","s2","s3","s4","s5"].forEach((s,i)=>$(s).classList.toggle("hide", i!==step-1));
  window.scrollTo({top:$("app").offsetTop-24,behavior:"smooth"});
}
