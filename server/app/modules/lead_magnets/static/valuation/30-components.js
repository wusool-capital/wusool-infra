// ===== GATE COMPONENT =====
function Gate({onSubmit,apiKey,setApiKey,submitting,alreadySubmitted}){
  const [f,setF]=useState({
    companyName:"",name:"",email:"",domain:"",description:"",
    sector:"",geo:"United Arab Emirates",
    revenue:"",profitBeforeTax:"",ownerSalary:"",
    raised:"",
    stage:"",lastRaiseRevenue:"",lastRaisePBT:"",
    consent:false
  });
  const [err,setErr]=useState({});
  const [gateCur,setGateCur]=useState("USD");
  const [enriching,setEnriching]=useState(false);
  const [enriched,setEnriched]=useState(false);
  const [descAutoFilled,setDescAutoFilled]=useState(false);
  const [sectorAutoFilled,setSectorAutoFilled]=useState(false);
  const [enrichFailed,setEnrichFailed]=useState(false);
  const descRef=useRef(null);

  // Auto-grow textarea whenever description changes
  useEffect(()=>{
    if(descRef.current){
      descRef.current.style.height="auto";
      descRef.current.style.height=(descRef.current.scrollHeight+2)+"px";
    }
  },[f.description]);

  // Comma-formatted number input helpers
  const fmtNumInput=v=>{
    if(v===''||v===undefined||v===null)return'';
    const s=String(v).replace(/,/g,'');
    if(s==='-'||s==='')return s;
    const n=parseFloat(s);
    if(isNaN(n))return v;
    const sign=n<0?'-':'';
    const abs=Math.abs(n);
    const parts=s.replace('-','').split('.');
    parts[0]=Math.floor(abs).toLocaleString('en-US');
    return sign+parts.join('.');
  };
  const chNum=e=>{
    const{name,value}=e.target;
    const stripped=value.replace(/,/g,'');
    if(stripped===''||stripped==='-'||/^-?\d*\.?\d*$/.test(stripped)){
      setF(p=>({...p,[name]:stripped}));
      setErr(p=>({...p,[name]:''}));
    }
  };

  // Auto-detect sector from description when user types
  const ch=e=>{
    const{name,value}=e.target;
    setF(p=>{
      const next={...p,[name]:value};
      if(name==="description"&&value.length>20){
        const inferred=detectSectorFromText(value);
        if(inferred&&!p.sector){next.sector=inferred;setSectorAutoFilled(true);}
      }
      return next;
    });
    setErr(p=>({...p,[name]:""}));
  };

  const enrichFromDomain=async(domain)=>{
    if(!domain)return;
    const clean=domain.replace(/^https?:\/\//,"").replace(/^www\./,"").split("/")[0].split("?")[0].trim().toLowerCase();
    if(!clean||clean.length<3)return;
    setEnriching(true);
    setEnrichFailed(false);
    const coName=clean.replace(/\.[a-z]{2,6}$/i,"").replace(/[-_.]/g," ");

    let desc="",sector="";
    try{
      const resp=await fetch("/enrich",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({domain:clean,company:coName})
      });
      if(resp.ok){
        const data=await resp.json();
        if(data.description)desc=data.description;
        if(data.sector&&ALL_SECTORS.includes(data.sector))sector=data.sector;
      }
    }catch(e){
      console.warn("Enrichment failed:",e);
    }

    // AI enrichment succeeded only if we got a real description back.
    // If it failed, do NOT invent a generic description; flag it so the user fills it in.
    const aiSucceeded=!!desc;

    setF(p=>({
      ...p,
      description:desc,
      sector:aiSucceeded?sector:""
    }));
    setTimeout(()=>{
      setDescAutoFilled(aiSucceeded);
      setSectorAutoFilled(aiSucceeded);
      setEnrichFailed(!aiSucceeded);
      setEnriched(true);
    },0);
    setEnriching(false);
  };

  const sub=e=>{
    e.preventDefault();const ne={};
    if(!f.companyName.trim())ne.companyName="Required";
    if(!f.name.trim())ne.name="Required";
    if(!f.email.trim()||!f.email.includes("@"))ne.email="Valid email required";
    if(!f.domain.trim())ne.domain="Domain is required";
    if(!f.sector)ne.sector="Required";
    if(!f.geo)ne.geo="Required";
    if(!f.revenue||parseFloat(f.revenue)<=0)ne.revenue="Valid revenue required";
    if(!f.raised)ne.raised="Please select Yes or No";
    if(!f.consent)ne.consent="Please accept the Privacy Policy to continue";
    if(Object.keys(ne).length){setErr(ne);return}
    const toUSD=v=>{const n=parseFloat(v)||0;return gateCur==="AED"?n/3.6725:n;};
    onSubmit({
      ...f,
      inputCurrency:gateCur,
      revenue:toUSD(f.revenue),
      profitBeforeTax:toUSD(f.profitBeforeTax),
      ownerSalary:toUSD(f.ownerSalary),
      lastRaiseRevenue:f.lastRaiseRevenue?toUSD(f.lastRaiseRevenue):null,
      lastRaisePBT:f.lastRaisePBT?toUSD(f.lastRaisePBT):null
    });
  };

  return(
    <div className="gate-bg">
      <div className="gate-card">
        <div style={{textAlign:"center",marginBottom:28}}><img src="../img/a0288d00.png" alt="Wusool Capital" style={{height:"44px",width:"auto"}}/></div>
        <h1 className="gate-title" style={{textAlign:"center"}}>Valuation Tool</h1>
        <p className="gate-sub" style={{textAlign:"center"}}>Get an institutional-grade valuation for your company in minutes</p>
        <form onSubmit={sub}>
          <div className="row2" style={{gridTemplateColumns:"1fr 1fr"}}>
            <div className="fg" style={{minWidth:0}}><label className="fl">Company Name *</label><input className="fi" name="companyName" value={f.companyName} onChange={ch} placeholder="e.g. Acme Corp"/>{err.companyName&&<div className="fe">{err.companyName}</div>}</div>
            <div className="fg" style={{minWidth:0}}><label className="fl">Your Name *</label><input className="fi" name="name" value={f.name} onChange={ch} placeholder="Full name"/>{err.name&&<div className="fe">{err.name}</div>}</div>
          </div>
          <div className="fg"><label className="fl">Email *</label><input className="fi" name="email" type="email" value={f.email} onChange={ch} placeholder="you@company.com"/>{err.email&&<div className="fe">{err.email}</div>}</div>
          <div className="fg">
            <label className="fl">
              Company Domain *
              {enriching&&<span className="enriching-badge"><span className="ai-loader-dots"><span>.</span><span>.</span><span>.</span></span> AI Analyzing</span>}
              {(!enriching&&enriched)&&<span className="ok-badge">&#x2713; Auto-filled</span>}
            </label>
            <input className={"fi"+(enriched?" enriched":"")} name="domain" value={f.domain} onChange={ch}
              onBlur={e=>enrichFromDomain(e.target.value)}
              placeholder="e.g. yourcompany.com"/>
            {err.domain?<div className="fe">{err.domain}</div>:<div className="fh">Enter your domain and we will auto-fill the description and industry</div>}
          </div>
          <div className="fg">
            <label className="fl">
              Company description
              {descAutoFilled&&<span className="ok-badge">&#x2713; Auto-filled</span>}
              <Tip text="A concise description helps us select the most relevant comparable companies and benchmarks."/>
            </label>
            <textarea ref={descRef} className={"fi"+(descAutoFilled&&f.description?" enriched":"")} name="description" value={f.description} onChange={ch} placeholder="e.g. We build AI-powered supply chain software for mid-market manufacturers" style={{minHeight:64,overflow:"hidden",resize:"none"}}/>
            {enrichFailed&&<div className="fh" style={{color:"#B45309",background:"#FEF3C7",border:"1px solid #FCD34D",borderRadius:8,padding:"8px 10px",marginTop:6}}>We could not auto-detect this company. Please write a short description and select the sector manually so we can match the right comparables.</div>}
          </div>
          <div className="row2" style={{gridTemplateColumns:"1fr 1fr"}}>
            <div className="fg" style={{minWidth:0}}>
              <label className="fl">
                Industry / Sector *
                {sectorAutoFilled&&<span className="ok-badge">&#x2713; Auto-filled</span>}
                <Tip text="Primary sector. Drives comparable company selection and growth benchmarks."/>
              </label>
              <select className={"fi"+(sectorAutoFilled&&f.sector?" enriched":"")} name="sector" value={f.sector} onChange={ch} style={{width:"100%"}}>
                <option value="">Select sector</option>
                {ALL_SECTORS.map(s=><option key={s} value={s}>{s}</option>)}
              </select>
              {err.sector&&<div className="fe">{err.sector}</div>}
            </div>
            <div className="fg" style={{minWidth:0}}>
              <label className="fl">Geography / HQ * <Tip text="Country of HQ. Affects tax rate and regional benchmarks."/></label>
              <select className="fi" name="geo" value={f.geo} onChange={ch} style={{width:"100%"}}>
                <option value="">Select country</option>
                {ALL_GEOS.map(g=><option key={g} value={g}>{g}</option>)}
              </select>
              {err.geo&&<div className="fe">{err.geo}</div>}
            </div>
          </div>
          <div className="sep"/>
          <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:16}}>
            <div className="gate-cur-toggle">
              {["USD","AED"].map(c=>(
                <button key={c} type="button" className={"gate-cur-btn"+(gateCur===c?" active":"")} onClick={()=>setGateCur(c)}>{c}</button>
              ))}
            </div>
          </div>
          <div className="fg">
            <label className="fl">Annual Revenue ({gateCur}) * <Tip text="Last 12 months of total revenue. Base for all revenue multiple calculations."/></label>
            <input className="fi input-blue" name="revenue" type="text" inputMode="numeric" value={fmtNumInput(f.revenue)} onChange={chNum} placeholder={gateCur==="AED"?"e.g. 7,346,000":"e.g. 2,000,000"}/>
            {err.revenue&&<div className="fe">{err.revenue}</div>}
          </div>
          <div className="fg">
            <label className="fl">Annual Profit Before Tax ({gateCur}) <Tip text="Profit before tax for the last 12 months. Used as an EBITDA proxy. Enter negative if loss-making."/></label>
            <input className="fi input-blue" name="profitBeforeTax" type="text" inputMode="numeric" value={fmtNumInput(f.profitBeforeTax)} onChange={chNum} placeholder="e.g. 400,000 (negative if loss-making)"/>
          </div>
          <div className="fg">
            <label className="fl">Owner / Founder Annual Salary ({gateCur}) <Tip text="Total annual salary drawn by owners. Added back to profit for a cleaner EBITDA estimate."/></label>
            <input className="fi input-blue" name="ownerSalary" type="text" inputMode="numeric" value={fmtNumInput(f.ownerSalary)} onChange={chNum} placeholder="e.g. 150,000"/>
          </div>
          <div className="sep"/>
          <div className="fg">
            <label className="fl">Has your company raised funding? *</label>
            <div style={{display:"flex",gap:10,marginTop:4}}>
              {["No","Yes"].map(opt=>(
                <label key={opt} style={{display:"flex",alignItems:"center",justifyContent:"center",gap:6,cursor:"pointer",padding:"10px 18px",border:"1.5px solid "+(f.raised===opt?"var(--sb)":"#e0e0e0"),borderRadius:8,flex:1,background:f.raised===opt?"#f0f4ff":"#fff",fontWeight:f.raised===opt?700:500,fontSize:14,transition:"all 0.15s"}}>
                  <input type="radio" name="raised" value={opt} checked={f.raised===opt} onChange={ch} style={{display:"none"}}/>{opt}
                </label>
              ))}
            </div>
            {err.raised&&<div className="fe">{err.raised}</div>}
          </div>
          {f.raised==="Yes"&&(
            <div className="fundraise-section">
              <div className="fg">
                <label className="fl">Funding Stage <Tip text="Your current or most recent funding stage."/></label>
                <select className="fi" name="stage" value={f.stage} onChange={ch}>
                  <option value="">Select stage</option>
                  {STAGES.map(s=><option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="row2" style={{gridTemplateColumns:"1fr 1fr"}}>
                <div className="fg" style={{minWidth:0}}>
                  <label className="fl">Annual Revenue at Last Fundraise ({gateCur}) <Tip text="Annual revenue at the time of your most recent round."/></label>
                  <input className="fi input-blue" name="lastRaiseRevenue" type="text" inputMode="numeric" value={fmtNumInput(f.lastRaiseRevenue)} onChange={chNum} placeholder="Optional"/>
                </div>
                <div className="fg" style={{minWidth:0}}>
                  <label className="fl">Profit Before Tax at Fundraise ({gateCur}) <Tip text="PBT at time of last raise."/></label>
                  <input className="fi input-blue" name="lastRaisePBT" type="text" inputMode="numeric" value={fmtNumInput(f.lastRaisePBT)} onChange={chNum} placeholder="Optional"/>
                </div>
              </div>
            </div>
          )}
          <div className="consent-check">
            <input type="checkbox" id="valConsent" checked={f.consent}
              onChange={e=>{const v=e.target.checked;setF(p=>({...p,consent:v}));setErr(p=>({...p,consent:""}));}}/>
            <label htmlFor="valConsent">I agree to Wusool's <a href="https://www.wusoolcapital.com/privacy-policy" target="_blank" rel="noopener">Privacy Policy</a> and consent to being contacted.</label>
          </div>
          {err.consent&&<div className="fe" style={{marginTop:8}}>{err.consent}</div>}
          {alreadySubmitted&&<div className="fe" style={{marginTop:8}}>Sorry, you've already completed this before.</div>}
          <button type="submit" className="btn-primary" style={{marginTop:20}} disabled={submitting}>{submitting?"Checking...":"Get My Valuation"}</button>
        </form>
      </div>
    </div>
  );
}


// ===== AUTO DCF MODULE =====
function DCFModule({gate,cfg,onUpdate}){
  const cur=(gate&&gate.inputCurrency)||"USD";
  const [open,setOpen]=useState(false);
  usePrintExpand(open,setOpen);
  const [wacc_inputs,setWaccInputs]=useState(null);
  const [termGrowth,setTermGrowth]=useState(2);
  const [pf,setPf]=useState([]);
  const [cash,setCash]=useState(0);
  const [debt,setDebt]=useState(0);
  const [initialized,setInitialized]=useState(false);
  const [damodSource,setDamodSource]=useState(null);

  useEffect(()=>{
    if(initialized||!gate)return;
    const sector=gate.sector||"";
    const bench=getDamodaranBenchmark(sector);
    const growth=getIndustryGrowth(sector);
    const taxRate=getTaxRate(gate.geo||"");
    const adjEBITDA=(gate.profitBeforeTax||0)+(gate.ownerSalary||0);
    const baseRev=gate.revenue||0;
    const baseMargin=baseRev>0?(adjEBITDA/baseRev)*100:5;
    const sizePrem=baseRev<5000000?5:baseRev<20000000?4:baseRev<100000000?3:2;
    const ke=bench?parseFloat(bench.ke.toFixed(2)):12;
    const kd=bench?parseFloat(bench.kd.toFixed(2)):6;
    if(bench)setDamodSource(bench.industry);
    setTermGrowth(growth.termGrowth);
    const yr=new Date().getFullYear();
    const rows=[];
    let prevRev=baseRev;
    const decels=[1,1,0.8,0.65,0.5];
    // For loss-making companies, model a path to profitability
    // Target a reasonable terminal margin based on sector (default 15%)
    const targetMargin=Math.max(growth.ebitMarginImpr*5+5,15);
    const isLossMaking=baseMargin<0;
    for(let i=0;i<5;i++){
      const projRev=prevRev*(1+(growth.revGrowth/100)*decels[i]);
      let projMargin;
      if(isLossMaking){
        // Converge from negative margin toward target margin over 5 years
        // Use an easing curve so improvement accelerates as the company scales
        const t=(i+1)/5;
        const eased=t*t; // quadratic easing
        projMargin=baseMargin+(targetMargin-baseMargin)*eased;
      }else{
        projMargin=baseMargin+(growth.ebitMarginImpr*(i+1));
      }
      const projEBITDA=projRev*(projMargin/100);
      const dep=projRev*(growth.daaPct/100);
      const ebit=projEBITDA-dep;
      const capex=projRev*(growth.capexPct/100);
      const nwc=Math.max((projRev-prevRev)*(growth.nwcPct/100),0);
      rows.push({label:yr+i,ebit:Math.round(ebit),dep:Math.round(dep),capex:Math.round(capex),nwc:Math.round(nwc)});
      prevRev=projRev;
    }
    setPf(rows);
    setWaccInputs({ke,kd,sp:sizePrem,eqVal:Math.max(baseRev*3,1000000),d:0,tax:taxRate});
    setInitialized(true);
  },[gate,initialized]);

  const wacc=useMemo(()=>{
    if(!wacc_inputs)return 0.12;
    const{ke,kd,sp,eqVal,d:dbt,tax}=wacc_inputs;
    const E=eqVal||1,D=dbt||0;
    return(E/(E+D))*(ke/100)+(D/(E+D))*(kd/100)*(1-(tax||20)/100)+(sp||3)/100;
  },[wacc_inputs]);

  const dcfCalc=useMemo(()=>{
    if(!pf.length||!wacc_inputs)return{rows:[],tv:0,ev:0,eqVal:0};
    const taxR=(wacc_inputs.tax||20)/100;
    const gR=(termGrowth||2)/100;
    let sumDFCF=0;
    const rows=pf.map((r,i)=>{
      const nopat=r.ebit*(1-taxR);
      const fcf=nopat+r.dep-r.capex-r.nwc;
      const df=1/Math.pow(1+wacc,i+1);
      const dfcf=fcf*df;
      sumDFCF+=dfcf;
      return{...r,nopat,fcf,df,dfcf};
    });
    const lastFCF=rows[rows.length-1]?rows[rows.length-1].fcf:0;
    const denom=Math.max(wacc-gR,0.001);
    const rawTV=(lastFCF*(1+gR))/denom/Math.pow(1+wacc,rows.length);
    // Floor terminal value: if projected FCF never turns positive, TV should not be a large negative drag
    const tv=lastFCF<0?0:rawTV;
    const ev=Math.max(sumDFCF+tv,0);
    const eqBeforeDlom=Math.max(ev+cash-(wacc_inputs.d||0),0);
    // Matches domain/valuation/valuation_methods.py's `_DEFAULT_DLOM_PCT` —
    // without it this report shows an equity value ~1.43x higher than the
    // blend actually written to Attio for the same submission.
    const eqV=eqBeforeDlom*(1-DLOM_PCT/100);
    return{rows,tv,ev,eqVal:eqV,sumDFCF,tvFloored:lastFCF<0};
  },[pf,wacc,wacc_inputs,termGrowth,cash]);

  useEffect(()=>{onUpdate({dcfEV:dcfCalc.ev,dcfEquity:dcfCalc.eqVal})},[dcfCalc.ev,dcfCalc.eqVal]);

  const chPf=(i,k,v)=>{const u=[...pf];u[i]={...u[i],[k]:v};setPf(u)};
  const chW=(k,v)=>setWaccInputs(p=>({...p,[k]:v}));

  if(!wacc_inputs)return null;
  return(
    <div className="mod">
      <div className="mod-hdr" onClick={()=>setOpen(!open)}>
        <div className="mod-title"><div className="mod-icon">1</div>DCF Analysis<span className="dcf-auto-badge">Auto-filled</span></div>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <span style={{fontSize:12,fontWeight:700,color:"var(--bb)"}}>{fmt(dcfCalc.eqVal,cur)}</span>
          <span className="mod-toggle">{open?"\u25BC":"\u25B6"}</span>
        </div>
      </div>
      {open&&<div className="mod-body">
        <div className="dcf-auto-note">
          DCF auto-filled using <strong>{gate.sector}</strong> industry benchmarks. WACC from Damodaran (NYU Stern Jan 2025). Revenue growth and margins from sector data. All figures are editable.
        </div>
        {(cfg.ebitda||0)<0&&<div style={{background:"rgba(240,48,84,0.07)",border:"1px solid rgba(240,48,84,0.2)",padding:"10px 14px",borderRadius:8,marginBottom:14,fontSize:12,color:"var(--sp)",lineHeight:1.5}}>
          <strong>Loss-making company:</strong> The DCF model assumes a path to profitability over the 5-year projection period, converging toward sector-typical margins. Early-year cash flows may remain negative. The terminal value reflects the projected steady-state economics. Review and adjust the EBIT projections below to match your operating plan.
        </div>}
        {damodSource&&<div className="damod-badge">
          <span style={{color:"var(--ng)",fontWeight:700}}>&#10003; Damodaran Applied</span>
          <span style={{color:"var(--gg)"}}>Industry: <strong style={{color:"var(--bb)"}}>{damodSource}</strong> -- NYU Stern Jan 2025</span>
        </div>}
        <div className="sub-hdr">WACC Inputs</div>
        <div className="cfg-grid">
          <div className="ib"><label>Cost of Equity (%) <Tip text="Auto-filled from Damodaran. Override if needed."/></label><NumInput className="fi input-blue" value={wacc_inputs.ke} onChange={v=>chW("ke",v)}/></div>
          <div className="ib"><label>Cost of Debt (%) <Tip text="Pre-tax cost of debt from Damodaran."/></label><NumInput className="fi input-blue" value={wacc_inputs.kd} onChange={v=>chW("kd",v)}/></div>
          <div className="ib"><label>Size Premium (%) <Tip text="Extra risk premium for smaller private companies. 2-5% typical."/></label><NumInput className="fi input-blue" value={wacc_inputs.sp} onChange={v=>chW("sp",v)}/></div>
          <div className="ib"><label>Tax Rate (%) <Tip text="Auto-set from geography. Override if needed."/></label><NumInput className="fi input-blue" value={wacc_inputs.tax} onChange={v=>chW("tax",v)}/></div>
          <div className="ib"><label>Terminal Growth (%)</label><NumInput className="fi input-blue" value={termGrowth} onChange={v=>setTermGrowth(v)}/></div>
          <div className="ib"><label>Computed WACC</label><input className="fi calc" readOnly value={fmtP(wacc*100)}/></div>
        </div>
        <div className="sub-hdr">5-Year Projections (auto-estimated, editable)</div>
        <div className="scroll-table">
        <table className="dt"><thead><tr><th>Year</th><th>EBIT</th><th>D&A</th><th>CAPEX</th><th>NWC</th><th>NOPAT</th><th>FCF</th><th>DF</th><th>Disc. FCF</th></tr></thead>
        <tbody>{dcfCalc.rows.map((r,i)=>(
          <tr key={i}><td>{r.label}</td>
          <td><NumInput value={pf[i]?pf[i].ebit:0} onChange={v=>chPf(i,"ebit",v)} style={{width:"100%"}}/></td>
          <td><NumInput value={pf[i]?pf[i].dep:0} onChange={v=>chPf(i,"dep",v)} style={{width:"100%"}}/></td>
          <td><NumInput value={pf[i]?pf[i].capex:0} onChange={v=>chPf(i,"capex",v)} style={{width:"100%"}}/></td>
          <td><NumInput value={pf[i]?pf[i].nwc:0} onChange={v=>chPf(i,"nwc",v)} style={{width:"100%"}}/></td>
          <td className="calc">{fmt(r.nopat,cur)}</td><td className="calc">{fmt(r.fcf,cur)}</td>
          <td className="calc">{r.df.toFixed(4)}</td><td className="calc">{fmt(r.dfcf,cur)}</td></tr>
        ))}</tbody></table>
        </div>
        <div className="sub-hdr">Bridge to Equity</div>
        <div className="cfg-grid">
          <div className="ib"><label>Cash on Hand ($)</label><NumInput className="fi input-blue" value={cash} onChange={v=>setCash(v)}/></div>
          <div className="ib"><label>Total Debt ($)</label><NumInput className="fi input-blue" value={debt} onChange={v=>{setDebt(v);chW("d",v)}}/></div>
        </div>
        <div style={{display:"flex",gap:12,marginTop:8}}>
          <div className="sum-card" style={{flex:1}}><div className="lbl">Terminal Value{dcfCalc.tvFloored?" (floored)":""}</div><div className="val">{fmt(dcfCalc.tv,cur)}</div></div>
          <div className="sum-card" style={{flex:1}}><div className="lbl">Enterprise Value</div><div className="val">{fmt(dcfCalc.ev,cur)}</div></div>
          <div className="sum-card accent" style={{flex:1}}><div className="lbl">Equity Value</div><div className="val">{fmt(dcfCalc.eqVal,cur)}</div></div>
        </div>
        {dcfCalc.tvFloored&&<div style={{fontSize:11,color:"var(--gg)",marginTop:8,lineHeight:1.5}}>Terminal value set to $0 because the projected Year 5 FCF remains negative. In practice, investors would value this company primarily on revenue multiples and market-based methods. Adjust the EBIT projections above to reflect your path to profitability.</div>}
      </div>}
    </div>
  );
}


// ===== TRADING COMPS MODULE =====
function TradingComps({gate,cfg,onUpdate,aiComps}){
  const cur=(gate&&gate.inputCurrency)||"USD";
  const [comps,setComps]=useState([]);
  const [dRev,setDRev]=useState(30);
  const [dEb,setDEb]=useState(30);
  const [open,setOpen]=useState(false);
  usePrintExpand(open,setOpen);
  const [initialized,setInitialized]=useState(false);

  useEffect(()=>{
    if(initialized)return;
    const sector=gate?gate.sector:"";
    const resolved=resolveSector(sector);
    let matches=PUBLIC_COMPS[sector]||PUBLIC_COMPS[resolved]||[];
    if(!matches.length){
      const mapped=SECTOR_TO_COMPS_KEY[sector]||SECTOR_TO_COMPS_KEY[resolved];
      if(mapped)matches=PUBLIC_COMPS[mapped]||[];
    }
    if(!matches.length){
      const words=sector.toLowerCase().split(/[\s&,]+/).filter(w=>w.length>2);
      for(const key of Object.keys(PUBLIC_COMPS)){
        if(words.some(w=>key.toLowerCase().includes(w))){matches=PUBLIC_COMPS[key];break}
      }
    }
    if(!matches.length)matches=[
      {co:"Microsoft Corp",tk:"MSFT",ev:3120000,rev:245000,ebitda:125000},
      {co:"Alphabet Inc",tk:"GOOG",ev:2050000,rev:340000,ebitda:110000},
      {co:"Apple Inc",tk:"AAPL",ev:3500000,rev:390000,ebitda:130000}
    ];
    setComps(matches.map(m=>({...m})));
    setInitialized(true);
  },[gate,initialized]);

  // Use AI comps when they arrive from App-level loader
  useEffect(()=>{
    if(aiComps&&aiComps.length>0){
      setComps(aiComps);
    }
  },[aiComps]);

  const negEbitda=(cfg.ebitda||0)<0;

  // Target revenue in $M, to compare against comps (which are in $M).
  const targetRevM=(cfg.revenue||0)/1e6;

  // Size discipline: public comps are typically orders of magnitude larger than
  // an SME. A $3M-revenue business does not trade at Duolingo's multiple. We
  // (a) flag when the median comp dwarfs the target, and (b) apply an additional
  // size discount that scales with how far the target sits below the comp set.
  const sizeInfo=useMemo(()=>{
    const valid=comps.filter(c=>c.rev>0);
    if(!valid.length||targetRevM<=0)return{ratio:0,sizeDisc:0,flag:false};
    const revs=valid.map(c=>c.rev).sort((a,b)=>a-b);
    const medComp=revs[Math.floor(revs.length/2)];
    const ratio=medComp/targetRevM; // how many times larger the median comp is
    // Size discount tiers (applied on top of the user's liquidity/haircut discount)
    let sizeDisc=0;
    if(ratio>=1000)sizeDisc=40;
    else if(ratio>=250)sizeDisc=30;
    else if(ratio>=50)sizeDisc=20;
    else if(ratio>=10)sizeDisc=10;
    return{ratio,sizeDisc,flag:ratio>=50};
  },[comps,targetRevM]);

  const calc=useMemo(()=>{
    const valid=comps.filter(c=>c.rev>0);
    const revM=valid.map(c=>c.ev/c.rev);
    const ebM=valid.filter(c=>c.ebitda>0).map(c=>c.ev/c.ebitda);
    const rS=getStats(revM),eS=getStats(ebM);
    // Combine user haircut, negative-EBITDA penalty, and size discount multiplicatively.
    const baseDRev=negEbitda?Math.min(dRev+20,100):dRev;
    const baseDEb=negEbitda?Math.min(dEb+20,100):dEb;
    const disc=(1-baseDRev/100)*(1-sizeInfo.sizeDisc/100);
    const discEb=(1-baseDEb/100)*(1-sizeInfo.sizeDisc/100);
    const adjDRev=Math.round((1-disc)*100);
    const adjDEb=Math.round((1-discEb)*100);
    return{rS,eS,adjDRev,adjDEb,revLow:rS.p25*disc,revMid:rS.median*disc,revHigh:rS.p75*disc,ebLow:eS.p25*discEb,ebMid:eS.median*discEb,ebHigh:eS.p75*discEb};
  },[comps,dRev,dEb,negEbitda,sizeInfo]);

  useEffect(()=>{onUpdate({trRevLow:calc.revLow,trRevMid:calc.revMid,trRevHigh:calc.revHigh,trEbLow:calc.ebLow,trEbMid:calc.ebMid,trEbHigh:calc.ebHigh})},[calc]);

  const ch=(i,k,v)=>{const u=[...comps];u[i]={...u[i],[k]:v};setComps(u)};

  return(
    <div className="mod">
      <div className="mod-hdr" onClick={()=>setOpen(!open)}>
        <div className="mod-title"><div className="mod-icon">2</div>Trading Comparables<span className="auto-badge">Auto-populated</span></div>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <span style={{fontSize:12,fontWeight:700,color:"var(--bb)"}}>{fmtM(calc.revMid)} EV/Rev</span>
          <span className="mod-toggle">{open?"\u25BC":"\u25B6"}</span>
        </div>
      </div>
      {open&&<div className="mod-body">
        <div style={{fontSize:12,color:"var(--gg)",marginBottom:12}}>Public comparables for <strong>{gate?gate.sector:""}</strong>. Figures in $M.</div>
        {negEbitda&&<div style={{background:"rgba(240,48,84,0.07)",padding:"8px 12px",borderRadius:6,marginBottom:10,fontSize:12,color:"var(--sp)",fontWeight:600}}>Negative EBITDA: +20% surcharge applied</div>}

        <div className="scroll-table">
        <table className="dt"><thead><tr><th>Company</th><th>Ticker</th><th>EV ($M)</th><th>Rev ($M)</th><th>EBITDA ($M)</th><th>EV/Rev</th><th>EV/EBITDA</th><th></th></tr></thead>
        <tbody>{comps.map((c,i)=>{
          const er=c.rev>0?c.ev/c.rev:null;const ee=c.ebitda>0?c.ev/c.ebitda:null;
          return(<tr key={i}>
            <td><input type="text" value={c.co} onChange={e=>ch(i,"co",e.target.value)} style={{minWidth:130}}/></td>
            <td><input type="text" value={c.tk} onChange={e=>ch(i,"tk",e.target.value)} style={{width:65}}/></td>
            <td><NumInput value={c.ev} onChange={v=>ch(i,"ev",v)} style={{width:"100%"}}/></td>
            <td><NumInput value={c.rev} onChange={v=>ch(i,"rev",v)} style={{width:"100%"}}/></td>
            <td><NumInput value={c.ebitda} onChange={v=>ch(i,"ebitda",v)} style={{width:"100%"}}/></td>
            <td className="calc">{fmtM(er)}</td><td className="calc">{fmtM(ee)}</td>
            <td><button onClick={()=>setComps(comps.filter((_,j)=>j!==i))} style={{background:"none",border:"none",color:"var(--sp)",cursor:"pointer",fontSize:14}}>x</button></td>
          </tr>);
        })}</tbody></table>
        </div>
        <button className="btn-sm btn-add" onClick={()=>setComps([...comps,{co:"",tk:"",ev:0,rev:0,ebitda:0}])}>+ Add Comparable</button>
        <div className="divider">
          <div className="row2">
            <div className="ib"><label>EV/Rev Discount (%) <Tip text="Private co. illiquidity discount vs public peers. Typically 20-40%."/></label><NumInput className="fi input-blue" value={dRev} onChange={v=>setDRev(v)}/><div className="fh">Effective: {calc.adjDRev}%</div></div>
            <div className="ib"><label>EV/EBITDA Discount (%)</label><NumInput className="fi input-blue" value={dEb} onChange={v=>setDEb(v)}/><div className="fh">Effective: {calc.adjDEb}%</div></div>
          </div>
          <div style={{display:"flex",gap:10,marginTop:12}}>
            <div className="sum-card" style={{flex:1}}><div className="lbl">Disc. Median EV/Rev</div><div className="val">{fmtM(calc.revMid)}</div></div>
            <div className="sum-card" style={{flex:1}}><div className="lbl">Disc. Median EV/EBITDA</div><div className="val">{fmtM(calc.ebMid)}</div></div>
          </div>
        </div>
      </div>}
    </div>
  );
}


// ===== TRANSACTION COMPS MODULE =====
function TransactionComps({gate,cfg,onUpdate}){
  const cur=(gate&&gate.inputCurrency)||"USD";
  const [selected,setSelected]=useState(new Set());
  const [dRev,setDRev]=useState(40);
  const [dEb,setDEb]=useState(20);
  const [open,setOpen]=useState(false);
  usePrintExpand(open,setOpen);
  const [initialized,setInitialized]=useState(false);

  useEffect(()=>{
    if(initialized||!gate||!gate.sector)return;
    const matches=matchTransactions(gate.sector,15);
    if(matches.length){setSelected(new Set(matches));setInitialized(true)}
  },[gate,initialized]);

  const negEbitda=(cfg.ebitda||0)<0;

  const selectedList=useMemo(()=>[...selected].map((idx,i)=>{
    const r=MA_RAW[idx];
    return{idx,label:"Deal "+(i+1),sector:(r.v||"").split(",").map(s=>s.trim()).filter(Boolean).slice(0,2).join(", "),hq:r.h,date:r.d,ev:r.e,evRev:r.r,evEb:r.b};
  }),[selected]);

  const calc=useMemo(()=>{
    const revM=selectedList.filter(r=>r.evRev!=null&&r.evRev>0).map(r=>r.evRev);
    const ebM=selectedList.filter(r=>r.evEb!=null&&r.evEb>0).map(r=>r.evEb);
    const rS=getStats(revM),eS=getStats(ebM);
    const adjDRev=negEbitda?Math.min(dRev+20,100):dRev;
    const adjDEb=negEbitda?Math.min(dEb+20,100):dEb;
    const disc=1-adjDRev/100,discEb=1-adjDEb/100;
    return{rS,eS,adjDRev,adjDEb,revLow:rS.p25*disc,revMid:rS.avg*disc,revHigh:rS.p75*disc,ebLow:eS.p25*discEb,ebMid:eS.avg*discEb,ebHigh:eS.p75*discEb,count:selectedList.length};
  },[selectedList,dRev,dEb,negEbitda]);

  useEffect(()=>{onUpdate({txRevLow:calc.revLow,txRevMid:calc.revMid,txRevHigh:calc.revHigh,txEbLow:calc.ebLow,txEbMid:calc.ebMid,txEbHigh:calc.ebHigh})},[calc]);

  return(
    <div className="mod">
      <div className="mod-hdr" onClick={()=>setOpen(!open)}>
        <div className="mod-title"><div className="mod-icon">3</div>Transaction Comparables<span className="auto-badge">Auto-matched</span><span className="sel-count" style={{marginLeft:6}}>{calc.count} deals</span></div>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <span style={{fontSize:12,fontWeight:700,color:"var(--bb)"}}>{fmtM(calc.revMid)} EV/Rev</span>
          <span className="mod-toggle">{open?"\u25BC":"\u25B6"}</span>
        </div>
      </div>
      {open&&<div className="mod-body">
        <div className="anon-note">Transaction data is anonymized. {calc.count} deals matched for "{gate?gate.sector:""}".</div>
        {negEbitda&&<div style={{background:"rgba(240,48,84,0.07)",padding:"8px 12px",borderRadius:6,marginBottom:10,fontSize:12,color:"var(--sp)",fontWeight:600}}>Negative EBITDA: +20% surcharge applied</div>}
        {selectedList.length>0&&<>
          <div className="scroll-table">
          <table className="dt"><thead><tr><th></th><th>Reference</th><th>Sector</th><th>HQ</th><th>Date</th><th>EV ($M)</th><th>EV/Rev</th><th>EV/EBITDA</th></tr></thead>
          <tbody>{selectedList.map((r,i)=>(
            <tr key={i}>
              <td><button onClick={()=>{const s=new Set(selected);s.delete(r.idx);setSelected(s)}} style={{background:"none",border:"none",color:"var(--sp)",cursor:"pointer",fontSize:14}}>x</button></td>
              <td style={{fontWeight:600,fontSize:12}}>{r.label}</td>
              <td style={{fontSize:11,color:"var(--gg)"}}>{r.sector}</td>
              <td style={{fontSize:11}}>{r.hq}</td>
              <td style={{fontSize:11}}>{r.date}</td>
              <td>{r.ev!=null?"$"+r.ev.toLocaleString()+"M":"-"}</td>
              <td className="calc">{r.evRev!=null?fmtM(r.evRev):"-"}</td>
              <td className="calc">{r.evEb!=null?fmtM(r.evEb):"-"}</td>
            </tr>
          ))}</tbody></table>
          </div>
          <div className="divider">
            <div className="row2">
              <div className="ib"><label>EV/Rev Discount (%)</label><NumInput className="fi input-blue" value={dRev} onChange={v=>setDRev(v)}/><div className="fh">Effective: {calc.adjDRev}%</div></div>
              <div className="ib"><label>EV/EBITDA Discount (%)</label><NumInput className="fi input-blue" value={dEb} onChange={v=>setDEb(v)}/><div className="fh">Effective: {calc.adjDEb}%</div></div>
            </div>
          </div>
        </>}
        {selectedList.length===0&&<div style={{padding:20,textAlign:"center",color:"var(--gg)",fontSize:13}}>No matching transactions found for "{gate?gate.sector:""}".</div>}
      </div>}
    </div>
  );
}


// ===== INDUSTRY RESEARCH MODULE =====
function IndustryResearch({gate,cfg,onUpdate}){
  const cur=(gate&&gate.inputCurrency)||"USD";
  const [selected,setSelected]=useState(new Set());
  const [disc,setDisc]=useState(20);
  const [open,setOpen]=useState(false);
  usePrintExpand(open,setOpen);
  const [initialized,setInitialized]=useState(false);

  useEffect(()=>{
    if(initialized||!gate||!gate.sector)return;
    const matches=matchVCRounds(gate.sector,gate.stage||"");
    if(matches.length){setSelected(new Set(matches));setInitialized(true)}
  },[gate,initialized]);

  const selectedList=useMemo(()=>[...selected].map((idx,i)=>{
    const r=VC_RAW[idx];
    return{idx,label:"Round "+(i+1),sector:r.s,stage:r.st,hq:r.h,fm:r.fm,fw:r.fw};
  }),[selected]);

  const calc=useMemo(()=>{
    const fyM=selectedList.filter(r=>r.fm!=null).map(r=>r.fm);
    const fwM=selectedList.filter(r=>r.fw!=null).map(r=>r.fw);
    const avgFy=fyM.length?fyM.reduce((a,b)=>a+b,0)/fyM.length:0;
    const avgFw=fwM.length?fwM.reduce((a,b)=>a+b,0)/fwM.length:0;
    const blended=(avgFy+avgFw)/2||avgFy||avgFw;
    const allM=[...fyM,...fwM].filter(Boolean);
    const s=getStats(allM);
    const d=1-disc/100;
    return{avgFy,avgFw,blended,low:s.p25*d,mid:blended*d,high:s.p75*d,count:selectedList.length};
  },[selectedList,disc]);

  useEffect(()=>{onUpdate({indLow:calc.low,indMid:calc.mid,indHigh:calc.high})},[calc]);

  return(
    <div className="mod">
      <div className="mod-hdr" onClick={()=>setOpen(!open)}>
        <div className="mod-title"><div className="mod-icon">4</div>Industry Research Multiples<span className="auto-badge">Auto-matched</span><span className="sel-count" style={{marginLeft:6}}>{calc.count} rounds</span></div>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <span style={{fontSize:12,fontWeight:700,color:"var(--bb)"}}>{fmtM(calc.mid)} EV/Rev</span>
          <span className="mod-toggle">{open?"\u25BC":"\u25B6"}</span>
        </div>
      </div>
      {open&&<div className="mod-body">
        <div className="anon-note">VC financing benchmarks. {calc.count} rounds matched for {gate?gate.sector:""}.</div>
        {calc.count>0?<>
          <div style={{display:"flex",gap:10,margin:"12px 0"}}>
            <div className="stat-box" style={{flex:1}}><div className="stat-lbl">Avg FY Multiple</div><div className="stat-val">{fmtM(calc.avgFy)}</div></div>
            <div className="stat-box" style={{flex:1}}><div className="stat-lbl">Avg Fwd Multiple</div><div className="stat-val">{fmtM(calc.avgFw)}</div></div>
            <div className="stat-box" style={{flex:1}}><div className="stat-lbl">Blended</div><div className="stat-val">{fmtM(calc.blended)}</div></div>
          </div>
          <div className="ib"><label>Discount to VC Multiples (%)<Tip text="Discount to reflect fair market value vs. venture premium."/></label><NumInput className="fi input-blue" value={disc} onChange={v=>setDisc(v)}/></div>
        </>:<div style={{padding:20,textAlign:"center",color:"var(--gg)",fontSize:13}}>No VC rounds matched for "{gate?gate.sector:""}".</div>}
      </div>}
    </div>
  );
}


// ===== VALUATION SUMMARY (shown at TOP) =====
function ValuationSummary({gate,cfg,vd,unlocked=true}){
  const cur=(gate&&gate.inputCurrency)||"USD";
  const rev=cfg.revenue||0;
  const ebitda=cfg.ebitda||0;
  const hasEbitda=ebitda>0;

  const methods=useMemo(()=>{
    // clampRow ensures low <= mid <= high by sorting the three values
    const clampRow=r=>{const s=[r.low,r.mid,r.high].sort((a,b)=>a-b);return{...r,low:s[0],mid:s[1],high:s[2]};};
    const rows=[];
    const dcfEq=vd.dcfEquity||0;
    if(dcfEq>0)rows.push(clampRow({name:"DCF Analysis",low:dcfEq*0.75,mid:dcfEq,high:dcfEq*1.25,note:"Central +/- 25% sensitivity"}));
    if(vd.trRevMid>0&&rev>0)rows.push(clampRow({name:"Trading Comps (EV/Revenue)",low:(vd.trRevLow||0)*rev,mid:vd.trRevMid*rev,high:(vd.trRevHigh||0)*rev,note:fmtM(vd.trRevLow)+" - "+fmtM(vd.trRevHigh)+" x rev"}));
    if(hasEbitda&&vd.trEbMid>0)rows.push(clampRow({name:"Trading Comps (EV/EBITDA)",low:(vd.trEbLow||0)*ebitda,mid:vd.trEbMid*ebitda,high:(vd.trEbHigh||0)*ebitda,note:fmtM(vd.trEbLow)+" - "+fmtM(vd.trEbHigh)+" x EBITDA"}));
    if(vd.txRevMid>0&&rev>0)rows.push(clampRow({name:"Transaction Comps (EV/Revenue)",low:(vd.txRevLow||0)*rev,mid:vd.txRevMid*rev,high:(vd.txRevHigh||0)*rev,note:fmtM(vd.txRevLow)+" - "+fmtM(vd.txRevHigh)+" x rev"}));
    if(vd.indMid>0&&rev>0)rows.push(clampRow({name:"Industry Research (VC Rounds)",low:(vd.indLow||0)*rev,mid:vd.indMid*rev,high:(vd.indHigh||0)*rev,note:fmtM(vd.indLow)+" - "+fmtM(vd.indHigh)+" x rev"}));
    return rows;
  },[vd,rev,ebitda,hasEbitda]);

  const blended=useMemo(()=>{
    if(!methods.length)return{low:0,mid:0,high:0};
    // Average across all methods per tier — use the same set of methods for all three
    // so the arrays are always the same length and comparable
    const avg=arr=>arr.reduce((a,b)=>a+b,0)/arr.length;
    const raw={
      low:avg(methods.map(m=>m.low)),
      mid:avg(methods.map(m=>m.mid)),
      high:avg(methods.map(m=>m.high))
    };
    // Final clamp: sort to guarantee low <= mid <= high
    const s=[raw.low,raw.mid,raw.high].sort((a,b)=>a-b);
    return{low:s[0],mid:s[1],high:s[2]};
  },[methods]);

  // FREEZE: the AI-powered comps propagate into `vd` slightly after the results
  // reveal, which used to make the blended range shift between the summary and the
  // full report. We commit the blended value ONCE, after the method set has
  // stabilised (all expected methods in, or a 30s safety cap), and display the
  // frozen value everywhere so the two views can never disagree.
  const [frozen,setFrozen]=useState(null);
  const settleTimer=useRef(null);
  const capTimer=useRef(null);
  useEffect(()=>{
    if(frozen)return;
    if(!methods.length)return;
    // Debounce: wait 1.5s after the last change to `methods` before committing,
    // so late-arriving AI comps are included rather than freezing on a partial set.
    if(settleTimer.current)clearTimeout(settleTimer.current);
    settleTimer.current=setTimeout(()=>{
      setFrozen(blended);
    },1500);
    // Safety cap: never wait more than 30s total; commit whatever is present.
    if(!capTimer.current){
      capTimer.current=setTimeout(()=>{
        setFrozen(f=>f||blended);
      },30000);
    }
    return()=>{if(settleTimer.current)clearTimeout(settleTimer.current);};
  },[methods,blended,frozen]);

  const shown=frozen||blended;

  return(
    <div className="val-hero">
      <div className="val-hero-label">Implied Enterprise Value</div>
      <div className="val-hero-amount">
        {methods.length===0?"Computing...":(fmtResult(shown.low,cur)+" \u2013 "+fmtResult(shown.high,cur))}
      </div>
      <div className="val-hero-range">
        {methods.length>0&&("Mid-point: "+fmtResult(shown.mid,cur))}
      </div>
      <div className="val-hero-sub">Blended across {methods.length} method{methods.length!==1?"s":""} | {gate?gate.sector:""} | {new Date().toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"})}</div>
      {!hasEbitda&&methods.length>0&&<div style={{fontSize:11,opacity:0.6,marginTop:6,lineHeight:1.4}}>Note: Pre-profit company. Valuation weighted toward revenue-based methods. EBITDA multiples excluded.</div>}
      {methods.length>0&&<div style={unlocked?{}:{filter:"blur(2.5px)",pointerEvents:"none",userSelect:"none",opacity:0.7}}>
        <table className="range-table" style={{marginTop:20}}>
          <thead>
            <tr>
              <th>Valuation Method</th>
              <th>Lower</th>
              <th>Mid</th>
              <th>Upper</th>
              <th style={{fontSize:10,opacity:0.5}}>Basis</th>
            </tr>
          </thead>
          <tbody>
            <tr className="blended-row">
              <td>Blended (Equal Weight)</td>
              <td>{fmtResult(shown.low,cur)}</td>
              <td className="mid-col">{fmtResult(shown.mid,cur)}</td>
              <td>{fmtResult(shown.high,cur)}</td>
              <td style={{fontSize:10,opacity:0.7}}>Average of all methods</td>
            </tr>
            {methods.map((m,i)=>(
              <tr key={i}>
                <td>{m.name}</td>
                <td>{fmtResult(m.low,cur)}</td>
                <td className="mid-col">{fmtResult(m.mid,cur)}</td>
                <td>{fmtResult(m.high,cur)}</td>
                <td style={{fontSize:10,opacity:0.5}}>{m.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:10,marginTop:10}}>
          <div style={{fontSize:10,opacity:0.4}}>For informational purposes only. Not financial advice. Lower/Upper = p25/p75 multiples and DCF +/-25% sensitivity.</div>
          <PDFExportButton gate={gate} cfg={cfg} vd={vd}/>
        </div>
      </div>}
    </div>
  );
}


// ===== INPUTS CONFIRMATION =====
function InputsCard({gate,cfg}){
  const adjEBITDA=(gate.profitBeforeTax||0)+(gate.ownerSalary||0);
  return(
    <div className="inputs-card">
      <div style={{fontSize:12,fontWeight:700,color:"var(--gg)",textTransform:"uppercase",letterSpacing:"0.5px",marginBottom:12}}>Inputs Summary</div>
      <div className="inputs-grid">
        <div className="inputs-item"><div className="lbl">Company</div><div className="val">{gate.companyName}</div></div>
        <div className="inputs-item"><div className="lbl">Sector</div><div className="val">{gate.sector}</div></div>
        <div className="inputs-item"><div className="lbl">Geography</div><div className="val">{gate.geo}</div></div>
        <div className="inputs-item"><div className="lbl">Annual Revenue</div><div className="val blue">{fmt(cfg.revenue,"USD")}</div></div>
        <div className="inputs-item"><div className="lbl">Profit Before Tax</div><div className="val blue">{fmt(gate.profitBeforeTax||0,"USD")}</div></div>
        <div className="inputs-item"><div className="lbl">Owner Salary</div><div className="val blue">{fmt(gate.ownerSalary||0,"USD")}</div></div>
        <div className="inputs-item"><div className="lbl">Adj. EBITDA Proxy</div><div className="val blue">{fmt(adjEBITDA,"USD")}</div></div>
        {gate.raised==="Yes"&&gate.stage&&<div className="inputs-item"><div className="lbl">Funding Stage</div><div className="val">{gate.stage}</div></div>}
        {gate.raised==="Yes"&&gate.lastRaiseRevenue&&<div className="inputs-item"><div className="lbl">Rev at Last Raise</div><div className="val blue">{fmt(gate.lastRaiseRevenue,"USD")}</div></div>}
      </div>
    </div>
  );
}


// ===== LINKEDIN PAYWALL GATE V2 =====
// Before unlock: shows generic strategic analysis preview + LinkedIn gate
// After unlock: removes preview, runs AI strategic analysis + all modules
function LinkedInGateV2({gate,cfg,aiComps,onUpdate,vd,unlocked,analysis}){
  return(
    <div>
      <div data-scroll-stop><StrategicAnalysis gate={gate} analysis={analysis}/></div>
      <div data-scroll-stop><FundraiseReadiness gate={gate} fundraise={analysis&&analysis.fundraise}/></div>
      <div data-scroll-stop><DCFModule gate={gate} cfg={cfg} onUpdate={onUpdate}/></div>
      <div data-scroll-stop><TradingComps gate={gate} cfg={cfg} onUpdate={onUpdate} aiComps={aiComps}/></div>
      <div data-scroll-stop><TransactionComps gate={gate} cfg={cfg} onUpdate={onUpdate}/></div>
      <div data-scroll-stop><IndustryResearch gate={gate} cfg={cfg} onUpdate={onUpdate}/></div>
    </div>
  );
}

// ===== STRATEGIC ANALYSIS ENGINE =====
function generateStrategicAnalysis(gate,cfg){
  // ---- Signal detection from description + domain (drives pros/cons) ----
  const desc=gate.description||"";
  const descL=desc.toLowerCase();
  const sectorL=(gate.sector||"").toLowerCase();
  const combo=descL+" "+sectorL;
  const co=gate.companyName||"The company";

  const isPremium=/premium|luxury|high.end|bespoke|artisan|crafted|superior.quality|finest|exclusive.design/i.test(desc);
  const hasBrandHeritage=/heritage|tradition|legacy|inspired by|reimagined|years of|founded|storied|generation|\btrunk\b/i.test(desc);
  const isPersonalised=/personal|curated|tailored|bespoke|custom|individual|handpick/i.test(desc);
  const isSubscription=/subscription|membership|recurring|monthly plan|annual plan/i.test(desc);
  const isSustainable=/sustain|eco|green|ethical|responsible|organic|planet|carbon|circular/i.test(desc);
  const isInnovative=/innovat|disrupt|pioneer|\bfirst\b|transform|revolution|reinvent|reimagined/i.test(desc);
  const isMarketplace=/marketplace|two.sided|connect.*buyer|platform.*seller|network.*supplier/i.test(combo);
  const hasDataAI=/\bai\b|machine.learn|data.driven|intelligence|predictive|algorithm|personaliz/i.test(desc);
  const isB2BDesc=/enterprise|b2b|business.to.business|corporate|workforce/i.test(combo);
  const isPhysical=/hardware|device|manufactur|suitcase|luggage|apparel|garment|physical.product|goods\b/i.test(desc);
  const isSoftwareDigital=/software|platform|cloud|\bapp\b|digital|saas/i.test(combo);
  const hasCommunity=/community|network|social|members|\bclub\b|tribe/i.test(desc);
  const isNiche=/niche|specialist|boutique|curated|exclusive|artisan|bespoke/i.test(desc);
  const isTravelLifestyle=/travel|luggage|suitcase|journey|adventure|explorer|nomad|voyag/i.test(desc);
  const isFashionLifestyle=/fashion|apparel|clothing|wardrobe|\bstyle\b|outfit|\bwear\b/i.test(combo);
  const isConsumerBrand=/consumer|retail|shopper|direct.to|\bd2c\b|everyday/i.test(combo);
  const isGlobal=/global|international|worldwide|\bworld\b|cross.border/i.test(desc);

  // ---- PROS: entirely from description/domain signals, never from financials ----
  const proPool=[
    {cond:isPremium&&hasBrandHeritage,title:"Heritage craft narrative creates durable brand defensibility",body:"A brand rooted in both premium craftsmanship and heritage storytelling occupies emotional territory that well-funded competitors cannot replicate through marketing spend alone. This positioning converts customers into brand advocates and supports sustainable pricing premiums over commodity alternatives."},
    {cond:isPremium&&!hasBrandHeritage,title:"Premium positioning commands structural pricing power",body:"By operating in the premium segment, "+co+" competes on quality and brand identity rather than price, creating structural insulation from commodity-level competition and enabling higher gross margins than mass-market peers at comparable revenue scale."},
    {cond:hasBrandHeritage&&!isPremium,title:"Heritage narrative creates authentic, hard-to-replicate differentiation",body:"A brand story rooted in heritage or tradition occupies emotional territory that well-funded challengers cannot replicate through marketing spend alone, providing durable differentiation that transcends product features and resonates with quality-conscious consumers."},
    {cond:isPersonalised,title:"Personalisation creates compounding switching costs and retention leverage",body:"Products and services built around individual preferences develop switching costs that grow with each interaction, as the experience becomes increasingly tailored to the customer. This dynamic supports above-average retention rates, higher lifetime value, and word-of-mouth referral loops."},
    {cond:isSubscription,title:"Recurring revenue model converts transactions into a predictable annuity stream",body:"A subscription or membership structure provides revenue predictability that one-time transaction models cannot match, supporting reliable financial planning, higher customer lifetime value multiples, and a quality-of-earnings premium that is reflected directly in exit valuations."},
    {cond:hasDataAI,title:"Data and AI capabilities create a widening proprietary moat",body:"Businesses that convert user interactions into proprietary datasets and AI-driven personalisation build structural advantages that compound over time. The performance gap between "+co+"'s model and a new entrant's widens with every additional data point, making competitive displacement progressively more difficult."},
    {cond:isMarketplace,title:"Marketplace dynamics carry inherent network effect defensibility",body:"Two-sided platform mechanics create self-reinforcing defensibility: each incremental participant increases the platform's value for all others, making it structurally costly for buyers and sellers to migrate to a less liquid alternative and creating a compounding barrier to new entrant displacement."},
    {cond:isSustainable,title:"ESG alignment opens premium distribution channels and investor pools",body:"A demonstrably sustainable product or supply chain resonates with a structurally growing segment of high-intent consumers, while simultaneously unlocking access to ESG-mandated institutional investors and retail distribution partners who apply sustainability screens to product selection."},
    {cond:isTravelLifestyle,title:"Travel is a structurally growing, high-spend, aspirational category",body:"The travel goods market benefits from secular growth in global travel volumes, the accelerating premiumisation of everyday accessories, and the rise of a globally mobile affluent class. These tailwinds provide a supportive demand backdrop that a well-positioned brand can translate into above-market growth rates."},
    {cond:isFashionLifestyle&&!isTravelLifestyle,title:"Fashion and lifestyle brands command emotional loyalty that transcends product utility",body:"Consumer loyalty in fashion is driven by identity and self-expression rather than purely functional value, creating a brand-customer relationship that sustains repeat purchase rates through seasonal cycles and supports organic word-of-mouth acquisition at significantly lower cost than paid channels."},
    {cond:isB2BDesc,title:"Enterprise customers deliver contractual revenue visibility and embedded stickiness",body:"B2B and enterprise-facing revenue typically carries multi-year contracts, formal renewal processes, and embedded workflows that create high switching costs, producing predictable, high-quality revenue streams that command a premium over consumer-facing models at equivalent revenue scale."},
    {cond:isInnovative,title:"Innovation-led positioning establishes early category authority",body:"Pioneering a new product category or approach creates brand equity and customer mindshare that is structurally difficult to displace, as markets tend to associate category leadership with the first credible player even as competition intensifies. This first-mover premium can persist well beyond the initial innovation window."},
    {cond:hasCommunity,title:"Community-driven growth reduces structural reliance on paid acquisition",body:"A strong community or membership base generates organic referral loops and social proof that significantly reduce customer acquisition costs relative to pure paid digital marketing, creating a compounding advantage as the community grows and the brand's earned media value increases."},
    {cond:isNiche&&!isMarketplace,title:"Niche specialisation reduces competitive exposure and supports premium pricing",body:"Operating in a focused, specialist segment means "+co+" competes on depth of expertise and curation rather than scale, reducing exposure to commoditisation and enabling a premium pricing architecture that broader, less specialised competitors cannot credibly replicate."},
    {cond:isPhysical&&!isSoftwareDigital,title:"Physical product creates tangible brand touchpoints at every use occasion",body:"A physical product generates recurring, sensory brand reinforcement with every use, reinforcing brand identity and driving organic social sharing. This creates marketing leverage that pure digital products cannot achieve and builds emotional attachment that compounds into long-term loyalty."},
    {cond:isSoftwareDigital&&!isB2BDesc,title:"Digital delivery enables scalable global distribution with low marginal cost",body:"A software or digital platform model decouples revenue growth from proportional cost growth, enabling "+co+" to serve an expanding global customer base without the infrastructure investment required by physical or service-intensive business models."},
  ];

  const proFallbacks=[
    {title:"Clear value proposition in a defined and growing market",body:co+" articulates a focused, differentiated proposition within its addressable market - the foundation for both sustainable commercial traction and investor conviction. A well-defined value proposition reduces acquisition friction and supports premium positioning relative to less differentiated alternatives."},
    {title:"Brand identity that compounds in value with scale",body:"A distinct brand identity is a compounding asset that typically appreciates as revenue and customer reach grow, supporting pricing power, distribution leverage, and acquisition attractiveness over time. Strong brands consistently trade at a premium to commodity-positioned businesses at equivalent scale."},
    {title:"Sector positioned in a structural growth window",body:co+" operates in the "+gate.sector+" sector, which continues to attract significant consumer demand, investor capital, and M&A activity - providing a supportive macro backdrop for a disciplined execution-driven growth strategy."},
  ];

  // ---- CONS: entirely from description/domain signals, never from financials ----
  const conPool=[
    {cond:isPhysical,title:"Physical supply chain introduces inventory, margin, and logistics risk",body:"Managing a physical product requires ongoing capital allocation to inventory, exposure to freight cost volatility, supply chain disruption risk, and the operational complexity of quality control and returns management - all of which can compress margins and strain working capital at scale."},
    {cond:isFashionLifestyle||isTravelLifestyle,title:"Seasonal cycles and trend sensitivity create demand planning complexity",body:"Consumer preferences in fashion and lifestyle accessories shift across seasons and cultural moments, creating risk of unsold inventory that must be discounted or written off. Sophisticated demand forecasting and disciplined inventory management are non-negotiable operational capabilities at meaningful scale."},
    {cond:isConsumerBrand||isFashionLifestyle||isTravelLifestyle,title:"Rising paid digital acquisition costs erode consumer brand unit economics",body:"Consumer-facing brands are heavily exposed to increasing CPMs across Meta, Google, and TikTok advertising ecosystems, as well as algorithm changes that can suddenly impair channel performance. CAC inflation risk is structural and persistent, requiring ongoing diversification into owned and earned channels."},
    {cond:isNiche,title:"Niche specialisation constrains the total addressable market ceiling",body:"Deep specialisation, while protective, caps the scale of the addressable opportunity. Without a deliberate adjacency expansion strategy, "+co+" risks reaching a natural revenue ceiling that may limit its attractiveness to larger strategic acquirers who require material scale to justify a transaction."},
    {cond:isPremium,title:"Premium price points introduce cyclicality and volume sensitivity",body:"Premium-positioned products see disproportionate demand softening in economic downturns as consumers trade down to more accessible alternatives. Managing this cyclicality requires product range diversification, geographic spread, or recurring revenue mechanics to smooth the earnings profile through cycles."},
    {cond:isB2BDesc,title:"Enterprise sales cycles are long, resource-intensive, and produce lumpy revenue",body:"Selling to enterprise customers involves multi-stakeholder procurement, extended evaluation periods, legal review cycles, and significant pre-sales investment. This creates lumpy revenue recognition, unpredictable short-term performance, and high cost-of-sale that must be carefully managed against deal-level economics."},
    {cond:isMarketplace,title:"Achieving marketplace liquidity requires capital-intensive bilateral scaling",body:"Building density on both sides of a marketplace simultaneously demands significant upfront investment and patient capital, with the risk that the platform fails to achieve critical mass before funding is exhausted. The chicken-and-egg problem is a well-documented and costly challenge for early-stage marketplace models."},
    {cond:hasDataAI,title:"AI and data-intensive operations carry high talent costs and key-person risk",body:"Building and maintaining differentiated AI or data capabilities requires specialist engineering talent commanding significant compensation premiums in a globally competitive hiring market, creating persistent cost pressure, key-person dependency, and fragility if core technical contributors depart."},
    {cond:isTravelLifestyle,title:"Travel category carries macro disruption and cyclicality risk",body:"Demand for travel goods and accessories correlates strongly with travel volumes, which are subject to external shocks including economic downturns, geopolitical instability, and public health events. These disruptions can produce sudden, acute revenue pressure that is difficult to hedge operationally."},
    {cond:isSustainable,title:"Sustainability claims require rigorous verification and expose the brand to scrutiny",body:"ESG positioning creates reputational risk if supply chain practices, material sourcing, or manufacturing claims are challenged by media, regulators, or activist consumers. Robust third-party certification and transparent supply chain governance are essential to protecting the brand's sustainability credentials."},
    {cond:isSubscription,title:"Subscriber churn management demands continuous product and engagement investment",body:"Recurring revenue models are only valuable if churn remains controlled. Even a modest increase in monthly cancellation rates can erode the subscriber base materially over time, requiring constant investment in product value delivery, engagement mechanics, and proactive retention programmes."},
    {cond:isGlobal,title:"International operations introduce currency, regulatory, and localisation complexity",body:"Scaling across multiple geographies simultaneously exposes revenue to currency risk, demands localisation investment across language and cultural contexts, and requires navigation of divergent regulatory frameworks - all of which increase operational complexity and can dilute management bandwidth during critical growth phases."},
    {cond:isPhysical&&!isSoftwareDigital,title:"Working capital cycle for physical goods requires active cash management",body:"Physical product businesses carry inventory on balance sheet and face a timing gap between cash outflow (manufacturing, shipping) and cash inflow (customer payment). As the business scales, this working capital cycle can become a meaningful constraint on growth velocity without proactive financing management."},
  ];

  const conFallbacks=[
    {title:"Competitive intensity in "+gate.sector+" compresses differentiation windows",body:"The "+gate.sector+" space is attracting well-funded incumbents and new entrants investing aggressively in adjacent categories, requiring sustained product innovation, brand investment, and customer experience excellence to maintain a defensible competitive position."},
    {title:"Operational scaling carries execution risk at each growth stage",body:"The transition from current scale to the next revenue inflection point typically exposes gaps in team depth, systems architecture, and process maturity. Proactive investment in operational infrastructure before constraints become visible is critical to ensuring organisational capacity does not become the binding constraint on growth."},
    {title:"Customer acquisition and retention economics require ongoing optimisation",body:"Sustained revenue growth demands continuous refinement of acquisition channel mix, retention mechanics, and cohort-level unit economics to ensure that increasing scale does not erode the fundamental profitability of each incremental customer relationship. CAC inflation and churn creep are silent margin destroyers when left unmanaged."},
  ];

  const matchedPros=proPool.filter(p=>p.cond).slice(0,3);
  const finalPros=[...matchedPros];
  for(const fb of proFallbacks){if(finalPros.length>=3)break;finalPros.push(fb);}

  const matchedCons=conPool.filter(c=>c.cond).slice(0,3);
  const finalCons=[...matchedCons];
  for(const fb of conFallbacks){if(finalCons.length>=3)break;finalCons.push(fb);}

  // ---- INSIGHTS: from gate inputs only (financial data, geo, sector, funding stage) ----
  const rev=cfg.revenue||0;
  const ebitda=cfg.ebitda||0;
  const margin=rev>0?(ebitda/rev)*100:0;
  const geo=gate.geo||"";
  const raised=gate.raised==="Yes";
  const stage=gate.stage||"";
  const isGCCGeo=/uae|united arab emirates|saudi|qatar|bahrain|kuwait|oman|jordan/i.test(geo);
  const isB2BSector=/saas|cybersecurity|fintech|payments|logistics|supply chain|future of work/i.test(sectorL);

  const insightPool=[];
  if(margin<0){
    insightPool.push({title:"Path to profitability is the highest-priority near-term milestone",body:"At a negative EBITDA margin, every dollar of cost reduction has a disproportionate impact on valuation across all methodologies. A credible, time-bound roadmap to break-even - with specific operating levers identified - will unlock a material valuation re-rating and substantially improve terms at the next fundraising round."});
  } else if(margin>0&&margin<15){
    insightPool.push({title:"Margin expansion to 15-20%+ is the highest-value operational focus",body:"Moving from the current "+margin.toFixed(0)+"% EBITDA margin to a 15-20%+ profile could increase the implied valuation by 1.5-2.5x under EBITDA multiple methodologies, with no requirement to grow the top line. The priority sequence should be: pricing review, COGS renegotiation, then headcount efficiency."});
  } else if(margin>=15){
    insightPool.push({title:"Strong margins create capacity to invest aggressively in growth",body:"At "+margin.toFixed(0)+"% EBITDA margins, "+co+" has the operational leverage to reinvest in growth without deteriorating earnings quality. The strategic priority should shift to identifying the highest-ROI growth channels - geographic expansion, product adjacencies, or distribution partnerships - and deploying capital there with discipline."});
  }
  if(isGCCGeo){
    insightPool.push({title:"GCC-first depth before multi-region expansion",body:"Deepening penetration across GCC markets and codifying the operating playbook before entering higher-complexity regions (EU, US) will preserve capital and create a replicable, investable expansion blueprint. GCC-proven unit economics are increasingly valued by international growth investors as evidence of scalability."});
  }
  if(!raised&&rev<5e6){
    insightPool.push({title:"Institutional fundraising readiness: build the metrics story now",body:"Pre-Series A investors will require three to six months of demonstrable momentum: consistent MoM revenue growth, improving unit economics, and a repeatable go-to-market motion. Investing in the data infrastructure to track and present these metrics compellingly will compress the fundraising timeline and improve deal terms."});
  } else if(raised&&/series a|seed/i.test(stage)&&rev<10e6){
    insightPool.push({title:"Series B readiness requires demonstrating repeatability at scale",body:"Series B investors look for proof that the early-stage growth motion is repeatable and non-idiosyncratic. The key proof points are: NRR above 110% (if B2B), consistent new logo acquisition with declining CAC, and gross margin expansion. Building these metrics into the operating cadence now accelerates the next round."});
  }
  if(isB2BSector&&rev>=2e6){
    insightPool.push({title:"Net revenue retention expansion delivers higher ROI than new logo acquisition",body:"In B2B models, improving NRR from baseline to 120%+ through structured upsell, cross-sell, and expansion programmes is typically 3-5x more capital-efficient than acquiring new logos. At "+co+"'s current revenue scale, a focused account expansion motion should be the primary commercial priority."});
  }
  if(isTravelLifestyle||isFashionLifestyle||isPersonalised){
    insightPool.push({title:"Customer data infrastructure is the core long-term strategic asset",body:"Every customer interaction - purchase history, preferences, returns, browsing behaviour - is a data point that compounds into a proprietary personalisation engine. Investing in data capture and CRM infrastructure now creates a competitive moat that is structurally difficult for incumbents to replicate, and substantially increases the business's attractiveness to acquirers."});
  }

  const insightFallback={title:"Strategic distribution partnerships can accelerate the growth trajectory",body:"Identifying two to three non-competing platforms or channel partners with access to "+co+"'s target customer profile can materially compress the CAC curve while generating market validation signal that strengthens the next fundraising or M&A process. Prioritise partnerships offering co-marketing, embedded distribution, or data sharing benefits."};
  const insightFallback2={title:"Operational excellence as a compounding competitive differentiator",body:"Building repeatable, measurable operational processes across sales, customer success, and finance creates an advantage that compounds as the business scales and becomes increasingly difficult for less disciplined competitors to match. Operational excellence is the foundation of the margin expansion story that drives valuation multiple re-rating."};

  const finalInsights=insightPool.slice(0,2);
  if(finalInsights.length<1)finalInsights.push(insightFallback);
  if(finalInsights.length<2)finalInsights.push(insightFallback2);

  return{
    pros:finalPros.slice(0,3),
    cons:finalCons.slice(0,3),
    insights:finalInsights.slice(0,2)
  };
}

// ===== STRATEGIC ANALYSIS COMPONENT =====
// pros/cons/insights now come from the parent's single /analyze call
// (analysis prop) instead of a fetch of its own \u2014 /analyze always returns
// all three, from Bedrock or its deterministic fallback, so there is no
// separate loading/local-fallback state to manage here any more.
function StrategicAnalysis({gate,analysis}){
  const [open,setOpen]=useState(false);
  usePrintExpand(open,setOpen);

  if(!analysis){
    return(
      <div className="mod">
        <div className="mod-hdr" style={{cursor:"default"}}>
          <div className="mod-title"><div className="mod-icon" style={{background:"var(--sb)"}}>S</div>Strategic Analysis</div>
        </div>
        <div className="mod-body">
          <div className="ai-loader-wrap">
            <div className="ai-loader-ring"></div>
            <div className="ai-loader-brand">Wusool AI</div>
            <div className="ai-loader-status">Analyzing {gate.companyName||"company"}&apos;s strategic position<span className="ai-loader-dots"><span>.</span><span>.</span><span>.</span></span></div>
          </div>
        </div>
      </div>
    );
  }

  return(
    <div className="mod">
      <div className="mod-hdr" onClick={()=>setOpen(!open)}>
        <div className="mod-title"><div className="mod-icon" style={{background:"var(--sb)"}}>S</div>Strategic Analysis<span className="dcf-auto-badge">AI-powered</span></div>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <span style={{fontSize:12,fontWeight:500,color:"var(--gg)"}}>Based on {gate.companyName}'s profile</span>
          <span className="mod-toggle">{open?"\u25BC":"\u25B6"}</span>
        </div>
      </div>
      {open&&<div className="mod-body">
        <div className="strat-section">
          <div className="strat-section-title pros">
            <span>&#x2714;</span> 3 Strengths
          </div>
          {analysis.pros.map((p,i)=>(
            <div key={i} className="strat-item pro">
              <div className="strat-item-icon">+</div>
              <div className="strat-item-text"><strong>{p.title}</strong>{p.body}</div>
            </div>
          ))}
        </div>
        <div className="strat-section">
          <div className="strat-section-title cons">
            <span>&#x26A0;</span> 3 Risks &amp; Challenges
          </div>
          {analysis.cons.map((c,i)=>(
            <div key={i} className="strat-item con">
              <div className="strat-item-icon">-</div>
              <div className="strat-item-text"><strong>{c.title}</strong>{c.body}</div>
            </div>
          ))}
        </div>
        <div className="strat-section">
          <div className="strat-section-title insights">
            <span>&#x27A4;</span> Strategic Insights
          </div>
          {analysis.insights.map((s,i)=>(
            <div key={i} className="strat-item insight">
              <div className="strat-item-icon">&#x2192;</div>
              <div className="strat-item-text"><strong>{s.title}</strong>{s.body}</div>
            </div>
          ))}
        </div>
      </div>}
    </div>
  );
}



// ===== PDF EXPORT =====
function PDFExportButton({gate,cfg,vd,methods,blended}){
  const [exporting,setExporting]=useState(false);
  const handleExport=()=>{
    setExporting(true);
    setTimeout(()=>{
      window.print();
      setExporting(false);
    },300);
  };
  return(
    <button className="pdf-btn" onClick={handleExport} disabled={exporting}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
      {exporting?"Preparing...":"Export PDF"}
    </button>
  );
}

// ===== FUNDRAISE READINESS SCORECARD =====
// `fundraise` is /analyze's own fundraise key, passed down from the
// parent's single call — no fetch of its own. The backend prompt only
// scores revenue_scale/profitability/market_context (never
// revenue_progression/stage_readiness, which needed the client's own
// last-raise fields); activeDims below already tolerates a dimension
// being absent, so this needed no other change.
function FundraiseReadiness({fundraise}){
  const [open,setOpen]=useState(false);
  usePrintExpand(open,setOpen);

  const barColor=(score)=>score>=70?"var(--ng)":score>=45?"#f5a623":"var(--sp)";
  const gradeColor=(g)=>/^A/.test(g)?"var(--ng)":/^B/.test(g)?"#0066cc":/^C/.test(g)?"#f5a623":"var(--sp)";

  if(!fundraise){
    return(
      <div className="mod">
        <div className="mod-hdr" style={{cursor:"default"}}>
          <div className="mod-title"><div className="mod-icon" style={{background:"var(--sb)"}}>M</div>M&amp;A Readiness Scorecard</div>
        </div>
        <div className="mod-body">
          <div className="ai-loader-wrap">
            <div className="ai-loader-ring"></div>
            <div className="ai-loader-brand">Wusool AI</div>
            <div className="ai-loader-status">Evaluating M&amp;A readiness<span className="ai-loader-dots"><span>.</span><span>.</span><span>.</span></span></div>
          </div>
        </div>
      </div>
    );
  }
  const result=fundraise;

  // Build display dimensions dynamically from what was returned
  const dimLabels={
    revenue_scale:"Revenue Scale",
    profitability:"Profitability",
    revenue_progression:"Revenue Progression",
    stage_readiness:"Stage Readiness",
    market_context:"Market Context"
  };
  const activeDims=Object.keys(dimLabels).filter(k=>result[k]&&typeof result[k].score==="number");

  return(
    <div className="mod">
      <div className="mod-hdr" onClick={()=>setOpen(!open)}>
        <div className="mod-title"><div className="mod-icon" style={{background:"var(--sb)"}}>M</div>M&amp;A Readiness Scorecard<span className="dcf-auto-badge">AI-powered</span></div>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <span style={{fontSize:13,fontWeight:700,color:gradeColor(result.overall_grade||"C")}}>{result.overall_grade||"N/A"}</span>
          <span className="mod-toggle">{open?"\u25BC":"\u25B6"}</span>
        </div>
      </div>
      {open&&<div className="mod-body">
        <div style={{textAlign:"center",marginBottom:20}}>
          <div className="scorecard-letter" style={{color:gradeColor(result.overall_grade||"C")}}>{result.overall_grade||"N/A"}</div>
          <div className="scorecard-label">{result.overall_label||"Assessment Complete"}</div>
        </div>
        {activeDims.map(key=>{
          const item=result[key];
          return(
            <div key={key} className="scorecard-bar-wrap">
              <div className="scorecard-bar-label"><span>{dimLabels[key]}</span><span style={{color:barColor(item.score)}}>{item.score}/100</span></div>
              <div className="scorecard-bar-track"><div className="scorecard-bar-fill" style={{width:item.score+"%",background:barColor(item.score)}}/></div>
              <div style={{fontSize:11,color:"var(--gg)",marginTop:3}}>{item.note}</div>
            </div>
          );
        })}
        {result.summary&&<div className="scorecard-summary">{result.summary}</div>}
      </div>}
    </div>
  );
}

// ===== RESULTS LOADING SCREEN =====
function ResultsLoadingScreen({gate,compsStatus}){
  const [elapsed,setElapsed]=useState(0);
  useEffect(()=>{
    const t=setInterval(()=>setElapsed(s=>s+1),1000);
    return()=>clearInterval(t);
  },[]);

  const steps=[
    {label:"Analyzing financial inputs",threshold:0},
    {label:"Computing DCF projections",threshold:2},
    {label:"Matching transaction comparables",threshold:4},
    {label:"Sourcing AI-powered trading comps",threshold:5},
    {label:"Calibrating valuation ranges",threshold:7}
  ];

  const compsLoaded=compsStatus==="done"||compsStatus==="fallback";
  const allDone=compsLoaded&&elapsed>=9;

  const getStepState=(step,i)=>{
    if(elapsed>=step.threshold+2)return "done";
    if(i===4&&compsLoaded&&elapsed>=step.threshold)return allDone?"done":"active";
    if(elapsed>=step.threshold)return elapsed>=step.threshold+2?"done":"active";
    return "pending";
  };

  return(
    <div className="results-loader-wrap">
      <div className="results-loader-card">
        <div className="results-loader-ring-wrap">
          <div className="results-loader-outer"></div>
          <div className="results-loader-inner"></div>
        </div>
        <div className="results-loader-title">Building Your Valuation</div>
        <div className="results-loader-status">
          {gate.companyName} | {gate.sector}
        </div>
        <div className="results-loader-steps">
          {steps.map((step,i)=>{
            const state=getStepState(step,i);
            return(
              <div key={i} className={"results-loader-step "+state}>
                <div className="results-loader-step-icon">
                  {state==="done"?"\u2713":state==="active"?<div className="results-loader-step-mini-spin"/>:""}
                </div>
                <span>{step.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}


// ===== LOCKED PREVIEW (pre-unlock layout) =====
// Order: Strategic teaser (2 green bullets sharp + rest blurred) -> Valuation hero
// (big number sharp, table blurred) -> remaining module titles sharp, bodies blurred.
function LockedPreview({gate,cfg,vd,teaserData}){
  const localPrev=useMemo(()=>(gate&&cfg)?generateStrategicAnalysis(gate,cfg):null,[gate,cfg]);

  const teaser=teaserData;
  const tLoading=!teaser;

  const strengths=(teaser&&teaser.strengths&&teaser.strengths.length?teaser.strengths:(localPrev?localPrev.pros:[]))||[];
  const risks=(teaser&&teaser.risks&&teaser.risks.length?teaser.risks:(localPrev?localPrev.cons:[]))||[];
  const insights=(teaser&&teaser.insights&&teaser.insights.length?teaser.insights:(localPrev?localPrev.insights:[]))||[];
  const greenBullets=strengths.slice(0,2);
  const blurredRisk=risks[0];
  const blurredInsight=insights[0];

  const otherSections=[
    {icon:"M",title:"M&A Readiness Scorecard",sub:"Transaction readiness across 6 weighted dimensions"},
    {icon:"D",title:"DCF Analysis",sub:"5-year discounted cash flow with sensitivity"},
    {icon:"T",title:"Trading Comparables",sub:"Listed-peer multiples benchmarking"},
    {icon:"X",title:"Transaction Comparables",sub:"Precedent M&A deal multiples"},
    {icon:"I",title:"Industry Research",sub:"Sector VC rounds and funding benchmarks"}
  ];

  return(
    <div style={{paddingBottom:280}}>
      {/* 1. STRATEGIC ANALYSIS - 2 green bullets sharp, rest blurred */}
      <div className="strat-wrap" style={{marginBottom:16}}>
        <div className="strat-hdr">
          <h3>Strategic Analysis</h3>
          <p>AI-powered assessment of {gate.companyName||"your business"}</p>
        </div>
        <div className="strat-body" style={{padding:"16px 20px"}}>
          {tLoading?(
            <div className="ai-loader-status" style={{padding:"12px 0"}}>Analyzing {gate.companyName||"company"}&apos;s strategic position<span className="ai-loader-dots"><span>.</span><span>.</span><span>.</span></span></div>
          ):(
          <div>
            <div className="strat-section-title pros" style={{marginBottom:8}}><span>&#x2714;</span> Key Strengths</div>
            {greenBullets.map((b,i)=>(
              <div key={i} className="strat-item pro" style={{marginBottom:7,padding:"9px 12px"}}>
                <div className="strat-item-icon">+</div>
                <div className="strat-item-text"><strong>{b.title}</strong><span style={{display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical",overflow:"hidden"}}>{b.body}</span></div>
              </div>
            ))}
            {/* Remainder - subheaders sharp like Key Strengths, only the bullets blurred and clamped short */}
            <div style={{marginTop:10}}>
              <div className="strat-section-title cons" style={{marginBottom:7}}><span>&#x26A0;</span> Risks &amp; Challenges</div>
              {blurredRisk&&(
                <div style={{filter:"blur(4.5px)",pointerEvents:"none",userSelect:"none",opacity:0.6,marginBottom:10,maxHeight:38,overflow:"hidden"}} aria-hidden="true">
                  <div className="strat-item con" style={{marginBottom:0,padding:"9px 12px"}}>
                    <div className="strat-item-icon">-</div>
                    <div className="strat-item-text"><strong>{blurredRisk.title}</strong>{blurredRisk.body}</div>
                  </div>
                </div>
              )}
              <div className="strat-section-title insights" style={{marginBottom:7}}><span>&#x27A4;</span> Strategic Insight</div>
              {blurredInsight&&(
                <div style={{filter:"blur(4.5px)",pointerEvents:"none",userSelect:"none",opacity:0.6,maxHeight:38,overflow:"hidden"}} aria-hidden="true">
                  <div className="strat-item insight" style={{marginBottom:0,padding:"9px 12px"}}>
                    <div className="strat-item-icon">&#x2192;</div>
                    <div className="strat-item-text"><strong>{blurredInsight.title}</strong>{blurredInsight.body}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
          )}
        </div>
      </div>

      {/* 2. VALUATION HERO - big number sharp, breakdown table blurred */}
      <div id="locked-valuation-hero" data-scroll-stop>
        <ValuationSummary gate={gate} cfg={cfg} vd={vd} unlocked={false}/>
      </div>

      {/* 3. REMAINING MODULES - titles sharp, bodies blurred */}
      <div style={{marginTop:16}}>
        {otherSections.map((s,i)=>(
          <div key={i} className="mod" data-scroll-stop style={{marginBottom:12,border:"1px solid #ebebeb",borderRadius:8,overflow:"hidden",background:"#fff"}}>
            <div className="mod-hdr" style={{cursor:"default",padding:"14px 18px",borderBottom:"1px solid #f0f0f0"}}>
              <div className="mod-title"><div className="mod-icon" style={{background:"var(--sb)"}}>{s.icon}</div>{s.title}</div>
            </div>
            <div style={{position:"relative",padding:"16px 18px"}}>
              <div style={{filter:"blur(4px)",pointerEvents:"none",userSelect:"none",opacity:0.5}} aria-hidden="true">
                <div style={{fontSize:13,color:"#444",marginBottom:8}}>{s.sub}</div>
                <div style={{height:10,background:"#e8e8e8",borderRadius:4,marginBottom:8,width:"90%"}}/>
                <div style={{height:10,background:"#e8e8e8",borderRadius:4,marginBottom:8,width:"75%"}}/>
                <div style={{height:10,background:"#e8e8e8",borderRadius:4,width:"82%"}}/>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


// ===== SCROLL HINT (minimalist jump-to-hero indicator) =====
function ScrollHint(){
  const [progress,setProgress]=useState(0); // 0..1 scroll position
  const [atBottom,setAtBottom]=useState(false);
  useEffect(()=>{
    const onScroll=()=>{
      const doc=document.documentElement;
      const max=(doc.scrollHeight-window.innerHeight)||1;
      const p=Math.min(1,Math.max(0,window.scrollY/max));
      setProgress(p);
      setAtBottom(window.scrollY>=max-80);
    };
    onScroll();
    window.addEventListener("scroll",onScroll,{passive:true});
    window.addEventListener("resize",onScroll);
    return()=>{window.removeEventListener("scroll",onScroll);window.removeEventListener("resize",onScroll);};
  },[]);
  // Purely a scroll-position indicator, not a button: `window.scrollTo`/
  // `window.scrollY` here would be the embedding iframe's own window, which
  // never scrolls once `shared/height.js` has resized it to fit all
  // content — the real host page is what actually scrolls. Clicking could
  // therefore never do anything, so it isn't offered as clickable.
  return(
    <div className="scroll-hint" aria-hidden="true">
      <span className="sh-label">{atBottom?"Top":"Scroll"}</span>
      <span className="sh-track"><span className="sh-fill" style={{height:(progress*100)+"%"}}/></span>
      <span className={"sh-chev"+(atBottom?" sh-chev-up":"")}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
      </span>
    </div>
  );
}


