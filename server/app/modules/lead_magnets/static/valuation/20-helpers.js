

// Info tooltip component
function Tip({text}){return(<span className="tip-wrap"><span className="tip-i">i</span><span className="tip-box">{text}</span></span>)}

// Forces a collapsible panel open for the duration of window.print(),
// restoring whatever state it was actually in afterward. Needed because
// every panel's body is render-gated (`{open&&<div>...}`), not merely
// CSS-hidden — window.print() only captures what's actually in the DOM at
// the moment it's called, so a collapsed panel's content is simply absent,
// and no `@media print` rule can bring back a node that was never rendered.
function usePrintExpand(open,setOpen){
  const openRef=useRef(open);
  useEffect(()=>{openRef.current=open},[open]);
  useEffect(()=>{
    let wasOpen=null;
    const before=()=>{wasOpen=openRef.current;setOpen(true)};
    const after=()=>{if(wasOpen!==null){setOpen(wasOpen);wasOpen=null}};
    window.addEventListener("beforeprint",before);
    window.addEventListener("afterprint",after);
    return()=>{window.removeEventListener("beforeprint",before);window.removeEventListener("afterprint",after)};
  },[]);
}

// Numeric input that handles negatives and intermediate typing states
function NumInput({value,onChange,className,style,step,min,max,placeholder,readOnly}){
  const [display,setDisplay]=useState(String(value||""));
  const ref=useRef(null);
  useEffect(()=>{if(document.activeElement!==ref.current)setDisplay(value===0?"0":String(value||""))},[value]);
  const handleChange=e=>{
    const raw=e.target.value;
    setDisplay(raw);
    if(raw===""||raw==="-"||raw==="."||(raw==="-.")){return}
    const n=parseFloat(raw);
    if(!isNaN(n))onChange(n);
  };
  const handleBlur=()=>{
    const n=parseFloat(display);
    if(isNaN(n)){setDisplay("0");onChange(0)}
    else{setDisplay(String(n));onChange(n)}
  };
  return <input ref={ref} type="text" inputMode="decimal" className={className||""} style={style} value={display} onChange={handleChange} onBlur={handleBlur} placeholder={placeholder} readOnly={readOnly}/>
}

// ===== UTILITIES =====
const fmt=(v,cur="USD")=>{if(v===null||v===undefined||isNaN(v))return"-";const sy=CUR_SYM[cur]||"$";const a=Math.abs(v);let s;if(a>=1e9)s=(a/1e9).toFixed(1)+"B";else if(a>=1e6)s=(a/1e6).toFixed(1)+"M";else if(a>=1e3)s=Math.round(a).toLocaleString();else s=a.toFixed(0);return v<0?`(${sy}${s})`:`${sy}${s}`};
const CUR_RATE={USD:1,AED:3.6725,SAR:3.75,GBP:0.79,EUR:0.92};
// Matches domain/valuation/valuation_methods.py's `_DEFAULT_DLOM_PCT`.
const DLOM_PCT=30;
const fmtResult=(v,cur="USD")=>{if(v===null||v===undefined||isNaN(v))return"-";const sy=CUR_SYM[cur]||"$";const converted=v*(CUR_RATE[cur]||1);const a=Math.abs(converted);let s;if(a>=1e9)s=(a/1e9).toFixed(1)+"B";else s=(a/1e6).toFixed(1)+"M";return converted<0?`(${sy}${s})`:`${sy}${s}`};
const fmtM=v=>{if(v===null||v===undefined||isNaN(v)||v===0)return"-";return v.toFixed(1)+"x"};
const fmtP=v=>{if(v===null||v===undefined||isNaN(v))return"-";return v.toFixed(2)+"%"};
const fmtN=v=>{if(v===null||v===undefined||isNaN(v))return"-";return Math.round(v).toLocaleString()};

function getStats(arr){
  if(!arr.length)return{min:0,p25:0,avg:0,median:0,p75:0,max:0};
  const s=[...arr].sort((a,b)=>a-b);const n=s.length;
  const p=q=>{const i=q*(n-1);const lo=Math.floor(i);const hi=Math.ceil(i);return lo===hi?s[lo]:s[lo]*(hi-i)+s[hi]*(i-lo)};
  return{min:s[0],p25:p(0.25),avg:s.reduce((a,b)=>a+b,0)/n,median:p(0.5),p75:p(0.75),max:s[n-1]};
}

// Match M&A transactions by sector
function matchTransactions(sector,limit=15){
  const resolved=resolveSector(sector);
  const scored=MA_RAW.map((r,i)=>{
    const verts=(r.v||"").toLowerCase();
    let score=0;
    if(verts.includes(sector.toLowerCase()))score+=3;
    if(verts.includes(resolved.toLowerCase()))score+=2;
    const sectorWords=sector.toLowerCase().split(/[\s&,]+/);
    sectorWords.forEach(w=>{if(w.length>2&&verts.includes(w))score+=1});
    return{idx:i,score};
  }).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,limit);
  return scored.map(x=>x.idx);
}

// Match VC rounds by sector and stage
function matchVCRounds(sector,stage){
  const resolved=resolveSector(sector);
  const scored=VC_RAW.map((r,i)=>{
    let score=0;
    if(r.s&&r.s.toLowerCase()===sector.toLowerCase())score+=3;
    if(r.s&&r.s.toLowerCase()===resolved.toLowerCase())score+=2;
    if(r.st&&stage&&r.st.toLowerCase()===stage.toLowerCase())score+=2;
    const sectorWords=sector.toLowerCase().split(/[\s&,]+/);
    sectorWords.forEach(w=>{if(w.length>2&&(r.s||"").toLowerCase().includes(w))score+=1});
    return{idx:i,score};
  }).filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
  return scored.map(x=>x.idx);
}


// ===== INDUSTRY GROWTH BENCHMARKS FOR AUTO-DCF =====
const INDUSTRY_GROWTH = {
  "AI":                     {revGrowth:42,ebitMarginImpr:6,daaPct:5,capexPct:7,nwcPct:3,termGrowth:3.5},
  "Pure-Play AI Software":  {revGrowth:45,ebitMarginImpr:5,daaPct:5,capexPct:7,nwcPct:3,termGrowth:3.5},
  "SaaS":                   {revGrowth:30,ebitMarginImpr:4,daaPct:5,capexPct:5,nwcPct:3,termGrowth:2.5},
  "Cybersecurity":          {revGrowth:28,ebitMarginImpr:4,daaPct:5,capexPct:6,nwcPct:3,termGrowth:2.5},
  "Fintech":                {revGrowth:35,ebitMarginImpr:4,daaPct:5,capexPct:6,nwcPct:4,termGrowth:3.0},
  "Payments":               {revGrowth:20,ebitMarginImpr:3,daaPct:5,capexPct:5,nwcPct:3,termGrowth:2.5},
  "Blockchain & Crypto":    {revGrowth:40,ebitMarginImpr:4,daaPct:5,capexPct:6,nwcPct:3,termGrowth:3.0},
  "E-commerce":             {revGrowth:22,ebitMarginImpr:2,daaPct:4,capexPct:5,nwcPct:5,termGrowth:2.0},
  "FoodTech":               {revGrowth:25,ebitMarginImpr:3,daaPct:5,capexPct:7,nwcPct:5,termGrowth:2.0},
  "Food Delivery":          {revGrowth:20,ebitMarginImpr:3,daaPct:5,capexPct:6,nwcPct:5,termGrowth:2.0},
  "Food & Beverages":       {revGrowth:10,ebitMarginImpr:1,daaPct:5,capexPct:8,nwcPct:5,termGrowth:2.0},
  "Healthcare":             {revGrowth:15,ebitMarginImpr:2,daaPct:5,capexPct:6,nwcPct:4,termGrowth:2.0},
  "Digital Health":         {revGrowth:28,ebitMarginImpr:4,daaPct:5,capexPct:6,nwcPct:3,termGrowth:2.5},
  "Healthtech":             {revGrowth:28,ebitMarginImpr:4,daaPct:5,capexPct:6,nwcPct:3,termGrowth:2.5},
  "EdTech":                 {revGrowth:22,ebitMarginImpr:3,daaPct:4,capexPct:5,nwcPct:3,termGrowth:2.0},
  "Edtech":                 {revGrowth:22,ebitMarginImpr:3,daaPct:4,capexPct:5,nwcPct:3,termGrowth:2.0},
  "Proptech":               {revGrowth:20,ebitMarginImpr:2,daaPct:5,capexPct:6,nwcPct:4,termGrowth:2.0},
  "Real Estate":            {revGrowth:12,ebitMarginImpr:1,daaPct:4,capexPct:8,nwcPct:4,termGrowth:2.0},
  "Logistics":              {revGrowth:15,ebitMarginImpr:2,daaPct:5,capexPct:7,nwcPct:4,termGrowth:2.0},
  "Supply Chain":           {revGrowth:18,ebitMarginImpr:2,daaPct:5,capexPct:6,nwcPct:4,termGrowth:2.0},
  "Mobility":               {revGrowth:30,ebitMarginImpr:5,daaPct:8,capexPct:12,nwcPct:5,termGrowth:2.5},
  "Media":                  {revGrowth:15,ebitMarginImpr:2,daaPct:6,capexPct:7,nwcPct:4,termGrowth:2.0},
  "Gaming":                 {revGrowth:18,ebitMarginImpr:2,daaPct:8,capexPct:10,nwcPct:3,termGrowth:2.0},
  "AgriTech":               {revGrowth:18,ebitMarginImpr:2,daaPct:6,capexPct:8,nwcPct:5,termGrowth:2.0},
  "Energy":                 {revGrowth:20,ebitMarginImpr:2,daaPct:8,capexPct:15,nwcPct:4,termGrowth:2.0},
  "Telecom":                {revGrowth:8, ebitMarginImpr:1,daaPct:10,capexPct:15,nwcPct:3,termGrowth:2.0},
  "DeepTech":               {revGrowth:35,ebitMarginImpr:8,daaPct:10,capexPct:15,nwcPct:5,termGrowth:3.0},
  "Insurance Brokers":      {revGrowth:15,ebitMarginImpr:2,daaPct:4,capexPct:4,nwcPct:3,termGrowth:2.0},
  "Hardware":               {revGrowth:12,ebitMarginImpr:1,daaPct:8,capexPct:10,nwcPct:5,termGrowth:2.0},
  "Future of Work":         {revGrowth:25,ebitMarginImpr:3,daaPct:5,capexPct:5,nwcPct:3,termGrowth:2.5},
  "Super App":              {revGrowth:35,ebitMarginImpr:5,daaPct:6,capexPct:8,nwcPct:4,termGrowth:3.0},
};

function getIndustryGrowth(sector){
  if(!sector)return{revGrowth:20,ebitMarginImpr:3,daaPct:5,capexPct:8,nwcPct:4,termGrowth:2.0};
  if(INDUSTRY_GROWTH[sector])return INDUSTRY_GROWTH[sector];
  const alias=SECTOR_ALIASES[sector];
  if(alias&&INDUSTRY_GROWTH[alias])return INDUSTRY_GROWTH[alias];
  const lower=sector.toLowerCase();
  for(const[k,v] of Object.entries(INDUSTRY_GROWTH)){
    if(lower.includes(k.toLowerCase())||k.toLowerCase().includes(lower))return v;
  }
  return{revGrowth:20,ebitMarginImpr:3,daaPct:5,capexPct:8,nwcPct:4,termGrowth:2.0};
}

function getTaxRate(geo){
  const t={
    "United Arab Emirates":9,"UAE":9,"Saudi Arabia":20,"KSA":20,
    "Egypt":22.5,"United Kingdom":25,"UK":25,"France":25,"Germany":30,
    "United States":21,"USA":21,"United States of America":21,
    "Singapore":17,"India":25,"Pakistan":29,"Nigeria":30,
    "South Africa":27,"Kenya":30,"Turkey":23,"Qatar":0,"Bahrain":0,
    "Kuwait":15,"Jordan":20,"Lebanon":17,"Morocco":31,"Tunisia":25
  };
  return t[geo]||20;
}

function detectSectorFromText(text){
  const t=(text||"").toLowerCase();
  // AI must come first - highly specific signals
  if(/\bai\b|artificial.intell|machine.learn|\bgpt\b|\bllm\b|deeplearn|neural.net|generative.ai|large.language/.test(t))return"AI";
  if(/cyber|firewall|endpoint.protect|malware|threat.detect|zero.trust|soc\b|siem\b/.test(t))return"Cybersecurity";
  // Fashion, styling, wardrobe, personal shopping - before generic retail
  if(/\bwardrobe\b|personal.styl|fashion.styl|outfit|clothing.subscription|apparel.box|style.box|curated.fashion|fashion.curat|closet.curate/.test(t))return"E-commerce";
  if(/fashion|clothing|apparel|garment|textile|footwear|\bshoes\b|\bboots\b|jewel|accessori|luxury.brand|designer.brand|ready.to.wear/.test(t))return"E-commerce";
  // Luggage, travel goods, and travel accessories
  if(/\bluggage\b|suitcase|travel.bag|carry.on|rolling.bag|travelware|travel.gear|travel.accessor|travel.essentials|\btrunk\b|hardshell|cabin.bag|checked.bag|packing.cube/.test(t))return"E-commerce";
  if(/restaurant(?!.*tech)|hospitality|hotel|resort|travel.booking|short.term.rental|vacation.rental|airbnb|tourism/.test(t))return"Food & Beverages";
  if(/food.delivery|meal.delivery|restaurant.tech|foodtech|\bdeliveroo\b/.test(t))return"FoodTech";
  if(/food.service|catering|bakery|grocery|supermarket|beverage|coffee.chain|\bqsr\b/.test(t))return"Food & Beverages";
  if(/saas|cloud.platform|b2b.software|enterprise.software|\bcrm\b|\berp\b|software.as.a.service/.test(t))return"SaaS";
  // BNPL must be checked before generic fintech to catch "split payments", "pay later" etc.
  if(/\bbnpl\b|buy.now.pay.later|buy now.{0,5}pay later|split.{0,10}(?:purchase|payment|instalment|installment)|pay.in.\d|pay later|interest.free.{0,20}(?:payment|instalment|installment)|deferred.payment|point.of.sale.financ/.test(t))return"Fintech";
  if(/fintech|neobank|digital.bank|challenger.bank|lending.platform|credit.platform|wealth.tech|wealthtech|insurtech/.test(t))return"Fintech";
  if(/\bpayment\b|checkout|billing|merchant.acqui|payment.gateway|payment.process/.test(t))return"Payments";
  if(/wallet|remittance|money.transfer/.test(t))return"Fintech";
  if(/ecommerce|e-commerce|online.marketplace|online.retail|direct.to.consumer|\bd2c\b|shopify.plus/.test(t))return"E-commerce";
  if(/marketplace|platform.connect|two.sided.market/.test(t))return"E-commerce";
  if(/digital.health|healthtech|telehealth|remote.care|remote.patient/.test(t))return"Digital Health";
  if(/health(?!.*edu)|medical|clinic|hospital|pharma|biotech|telemedicine|medtech/.test(t))return"Healthcare";
  if(/edtech|e-learning|online.learning|online.education|tutoring.platform|learning.management/.test(t))return"EdTech";
  if(/education|school|university|training.platform|course.platform|upskill/.test(t))return"EdTech";
  if(/logistics|shipping|freight|supply.chain|fleet.manag|last.mile|3pl\b/.test(t))return"Logistics";
  if(/proptech|property.tech|real.estate.tech|realty.platform/.test(t))return"Proptech";
  if(/real.estate|property.manag|commercial.real.estate/.test(t))return"Real Estate";
  if(/mobility|rideshare|ride.hail|electric.vehicle|\bev.platform\b|micro.mobility|autonomous.vehicle/.test(t))return"Mobility";
  if(/streaming|video.content|podcast.platform|content.creator|creator.economy/.test(t))return"Media";
  if(/media|news.platform|digital.publish|broadcast/.test(t))return"Media";
  if(/gaming|game.studio|esport|mobile.game|video.game/.test(t))return"Gaming";
  if(/agritech|agri.tech|precision.farm|crop.monitor|smart.farm/.test(t))return"AgriTech";
  if(/solar|renewable.energy|cleantech|climate.tech|carbon.credit|green.energy/.test(t))return"Energy";
  if(/energy(?!.*health)/.test(t))return"Energy";
  if(/telecom|telco|wireless.platform|broadband|isp\b|fiber.network/.test(t))return"Telecom";
  if(/quantum|robotics|3d.print|nano.tech|deep.tech|bioprint/.test(t))return"DeepTech";
  if(/insurance|insurtech|\bunderwriting\b|reinsurance/.test(t))return"Insurance Brokers";
  if(/blockchain|crypto.exchange|web3|defi|nft\b|digital.asset/.test(t))return"Blockchain & Crypto";
  if(/\biot\b|internet.of.things|embedded.system|smart.device|connected.device/.test(t))return"Hardware";
  if(/hardware|semiconductor|chip.design|pcb\b|electronic.component/.test(t))return"Hardware";
  if(/hr.tech|hrtech|recruitment.platform|talent.platform|workforce.manag|employee.benefit/.test(t))return"Future of Work";
  if(/super.app|all.in.one.platform|neobank.*marketplace/.test(t))return"Super App";
  return null;
}

