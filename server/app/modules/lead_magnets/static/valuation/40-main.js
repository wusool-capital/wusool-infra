// ===== APP =====
function App(){
  const [gated,setGated]=useState(false);
  const [gate,setGate]=useState(null);
  const [cfg,setCfg]=useState({revenue:0,ebitda:0});
  const [aiComps,setAiComps]=useState(null);
  const [aiCompsStatus,setAiCompsStatus]=useState("idle");
  const [resultsReady,setResultsReady]=useState(false);
  const [alreadySubmitted,setAlreadySubmitted]=useState(false);
  const [gateSubmitting,setGateSubmitting]=useState(false);
  // Never set anywhere — the report stays permanently locked, matching
  // readiness's gate. See the "Get Your Free Valuation Report Now" link.
  const [reportUnlocked]=useState(false);
  const [analyzeData,setAnalyzeData]=useState(null);
  const [analyzeStatus,setAnalyzeStatus]=useState("idle");
  const [vd,setVd]=useState({
    dcfEV:0,dcfEquity:0,
    trRevLow:0,trRevMid:0,trRevHigh:0,
    trEbLow:0,trEbMid:0,trEbHigh:0,
    txRevLow:0,txRevMid:0,txRevHigh:0,
    txEbLow:0,txEbMid:0,txEbHigh:0,
    indLow:0,indMid:0,indHigh:0
  });

  // Records the lead (and checks for a repeat) the moment the visitor
  // submits the gate form — not after /analyze and /compare finish. This
  // is the one place in the lead's life where an AI-enriched `comps` list
  // could still have been attached (the old flow waited for it), but a
  // duplicate check that only fires after the whole AI round trip is not
  // a duplicate check at the submit button, so it's sent empty here and
  // `value_company()`'s own static-sector fallback covers it — same
  // deterministic path a sweeper resume already uses.
  const handleGate=async data=>{
    setGateSubmitting(true);
    setAlreadySubmitted(false);
    try{
      const r=await fetch("/submit-lead",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          submission_id:(crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`),
          company:data.companyName||"",name:data.name||null,email:data.email||"",
          domain:data.domain||null,description:data.description||null,sector:data.sector||null,
          geography:data.geo||null,stage:data.stage||null,
          revenue:data.revenue||0,profit_before_tax:data.profitBeforeTax||null,
          owner_salary:data.ownerSalary||null,cash:0,debt:0,
          comps:[],consent:!!data.consent
        })
      });
      if(r.status===409){
        setAlreadySubmitted(true);
        setGateSubmitting(false);
        return;
      }
    }catch(e){
      // A recording failure must never block the visitor from seeing their
      // own report — only a confirmed 409 does that.
      console.warn("Lead submission failed:",e);
    }
    setGate(data);
    const adjEBITDA=(data.profitBeforeTax||0)+(data.ownerSalary||0);
    const cfgData={revenue:data.revenue,ebitda:adjEBITDA};
    setCfg(cfgData);
    setGated(true);
  };

  const upd=useCallback(u=>setVd(p=>({...p,...u})),[]);

  // /analyze: sector judgement, discounts, DCF overrides, the strategic
  // read (pros/cons/insights) and the fundraise scorecard, merged into one
  // call. Runs in parallel with /compare below, during the loading screen,
  // so the report is fully ready the moment loading ends (no second wait).
  // Sector-fit/discounts/DCF-override/search-term fields are in the
  // response but unused here - the live page never read the equivalent
  // client-composed fields either, so this is not a regression.
  useEffect(()=>{
    if(!gated||!gate)return;
    let cancelled=false;
    setAnalyzeStatus("loading");
    (async()=>{
      const adjEBITDA=(gate.profitBeforeTax||0)+(gate.ownerSalary||0);
      try{
        const resp=await fetch("/analyze",{
          method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            company:gate.companyName||"",domain:gate.domain||"",sector:gate.sector||"",
            description:gate.description||"",geography:gate.geo||"",
            revenue:gate.revenue||0,ebitda:adjEBITDA,
            raised:gate.raised==="Yes",stage:gate.stage||null
          })
        });
        const data=await resp.json();
        if(!cancelled){setAnalyzeData(data);setAnalyzeStatus("done");}
      }catch(e){
        console.warn("Analysis failed:",e);
        if(!cancelled)setAnalyzeStatus("done");
      }
    })();
    return()=>{cancelled=true;};
  },[gated,gate]);

  // /compare: comparable listed companies, grounded in search - the
  // replacement for the client's own web-search-powered comps call.
  useEffect(()=>{
    if(!gated||!gate)return;
    let cancelled=false;
    setAiCompsStatus("loading");
    (async()=>{
      try{
        const resp=await fetch("/compare",{
          method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            company:gate.companyName||"",sector:gate.sector||"",description:gate.description||"",
            revenue:gate.revenue||0,geography:gate.geo||""
          })
        });
        const data=await resp.json();
        if(cancelled)return;
        if(data.comps&&data.comps.length>=3){setAiComps(data.comps);setAiCompsStatus("done");}
        else setAiCompsStatus("fallback");
      }catch(e){
        console.warn("Comparables failed:",e);
        if(!cancelled)setAiCompsStatus("fallback");
      }
    })();
    return()=>{cancelled=true;};
  },[gated,gate]);

  // Failsafe: never let a hung /analyze call block the results reveal.
  useEffect(()=>{
    if(!gated)return;
    const failsafe=setTimeout(()=>{
      setAnalyzeStatus(s=>s==="done"?s:"done");
    },12000);
    return()=>clearTimeout(failsafe);
  },[gated]);


  const gateTimeRef=useRef(null);
  useEffect(()=>{
    if(gated&&!gateTimeRef.current)gateTimeRef.current=Date.now();
  },[gated]);

  useEffect(()=>{
    if(!gated)return;
    const compsFinished=aiCompsStatus==="done"||aiCompsStatus==="fallback";
    const analyzeFinished=analyzeStatus==="done";
    if(!compsFinished||!analyzeFinished)return;
    // Ensure minimum 10s loading display so all animation steps tick to done before reveal
    const elapsed=Date.now()-(gateTimeRef.current||Date.now());
    const minDelay=Math.max(10000-elapsed,1000);
    const timer=setTimeout(()=>setResultsReady(true),minDelay);
    return()=>clearTimeout(timer);
  },[gated,aiCompsStatus,analyzeStatus]);

  // Pre-compute initial valuation estimates so summary is stable before LinkedIn unlock
  useEffect(()=>{
    if(!gate)return;
    const sector=gate.sector||"";
    const baseRev=gate.revenue||0;
    const adjEBITDA=(gate.profitBeforeTax||0)+(gate.ownerSalary||0);
    const baseMargin=baseRev>0?(adjEBITDA/baseRev)*100:5;
    const negEbitda=adjEBITDA<0;

    // --- DCF pre-calc ---
    const bench=getDamodaranBenchmark(sector);
    const growth=getIndustryGrowth(sector);
    const taxRate=getTaxRate(gate.geo||"");
    const sizePrem=baseRev<5000000?5:baseRev<20000000?4:baseRev<100000000?3:2;
    const ke=bench?parseFloat(bench.ke.toFixed(2)):12;
    const kd=bench?parseFloat(bench.kd.toFixed(2)):6;
    const eqVal=Math.max(baseRev*3,1000000);
    const waccVal=(eqVal/(eqVal))*(ke/100)+(sizePrem||3)/100;
    const yr=new Date().getFullYear();
    const rows=[];
    let prevRev=baseRev;
    const decels=[1,1,0.8,0.65,0.5];
    // For loss-making companies, model a path to profitability
    const targetMargin=Math.max(growth.ebitMarginImpr*5+5,15);
    const isLossMaking=baseMargin<0;
    for(let i=0;i<5;i++){
      const projRev=prevRev*(1+(growth.revGrowth/100)*decels[i]);
      let projMargin;
      if(isLossMaking){
        const t=(i+1)/5;
        const eased=t*t;
        projMargin=baseMargin+(targetMargin-baseMargin)*eased;
      }else{
        projMargin=baseMargin+(growth.ebitMarginImpr*(i+1));
      }
      const projEBITDA=projRev*(projMargin/100);
      const dep=projRev*(growth.daaPct/100);
      const ebit=projEBITDA-dep;
      const capex=projRev*(growth.capexPct/100);
      const nwc=Math.max((projRev-prevRev)*(growth.nwcPct/100),0);
      rows.push({ebit:Math.round(ebit),dep:Math.round(dep),capex:Math.round(capex),nwc:Math.round(nwc)});
      prevRev=projRev;
    }
    const taxR=taxRate/100;
    const gR=(growth.termGrowth||2)/100;
    let sumDFCF=0;
    let lastFCF=0;
    rows.forEach((r,i)=>{
      const nopat=r.ebit*(1-taxR);
      const fcf=nopat+r.dep-r.capex-r.nwc;
      const df=1/Math.pow(1+waccVal,i+1);
      sumDFCF+=fcf*df;
      lastFCF=fcf;
    });
    const denom=Math.max(waccVal-gR,0.001);
    const rawTV=(lastFCF*(1+gR))/denom/Math.pow(1+waccVal,rows.length);
    const tv=lastFCF<0?0:rawTV;
    const dcfEV=Math.max(sumDFCF+tv,0);
    // Matches domain/valuation/valuation_methods.py's `_DEFAULT_DLOM_PCT` —
    // see the same fix in 30-components.js's `DCFModule`, which overwrites
    // this pre-calc once it mounts.
    const dcfEquity=Math.max(dcfEV,0)*(1-DLOM_PCT/100);

    // --- Transaction comps pre-calc ---
    const txMatches=matchTransactions(sector,15);
    const txList=txMatches.map(idx=>MA_RAW[idx]);
    const txRevM=txList.filter(r=>r.r!=null&&r.r>0).map(r=>r.r);
    const txEbM=txList.filter(r=>r.b!=null&&r.b>0).map(r=>r.b);
    const txRS=getStats(txRevM),txES=getStats(txEbM);
    const txDRev=negEbitda?Math.min(60,100):40;
    const txDEb=negEbitda?Math.min(40,100):20;
    const txDiscR=1-txDRev/100,txDiscE=1-txDEb/100;

    // --- Industry research pre-calc ---
    const vcMatches=matchVCRounds(sector,gate.stage||"");
    const vcList=vcMatches.map(idx=>VC_RAW[idx]);
    const fyM=vcList.filter(r=>r.fm!=null).map(r=>r.fm);
    const fwM=vcList.filter(r=>r.fw!=null).map(r=>r.fw);
    const avgFy=fyM.length?fyM.reduce((a,b)=>a+b,0)/fyM.length:0;
    const avgFw=fwM.length?fwM.reduce((a,b)=>a+b,0)/fwM.length:0;
    const blendedVC=(avgFy+avgFw)/2||avgFy||avgFw;
    const allVCM=[...fyM,...fwM].filter(Boolean);
    const vcS=getStats(allVCM);
    const vcDisc=0.8;

    setVd(p=>({...p,
      dcfEV,dcfEquity,
      txRevLow:txRS.p25*txDiscR,txRevMid:txRS.avg*txDiscR,txRevHigh:txRS.p75*txDiscR,
      txEbLow:txES.p25*txDiscE,txEbMid:txES.avg*txDiscE,txEbHigh:txES.p75*txDiscE,
      indLow:vcS.p25*vcDisc,indMid:blendedVC*vcDisc,indHigh:vcS.p75*vcDisc
    }));
  },[gate]);

  // Pre-compute trading comps from static data initially
  useEffect(()=>{
    if(!gate)return;
    const sector=gate.sector||"";
    const resolved=resolveSector(sector);
    const adjEBITDA=(gate.profitBeforeTax||0)+(gate.ownerSalary||0);
    const negEbitda=adjEBITDA<0;
    let compsData=PUBLIC_COMPS[sector]||PUBLIC_COMPS[resolved]||[];
    if(!compsData.length){
      const mapped=SECTOR_TO_COMPS_KEY[sector]||SECTOR_TO_COMPS_KEY[resolved];
      if(mapped)compsData=PUBLIC_COMPS[mapped]||[];
    }
    if(!compsData.length){
      const words=sector.toLowerCase().split(/[\s&,]+/).filter(w=>w.length>2);
      for(const key of Object.keys(PUBLIC_COMPS)){
        if(words.some(w=>key.toLowerCase().includes(w))){compsData=PUBLIC_COMPS[key];break}
      }
    }
    if(compsData.length){
      const valid=compsData.filter(c=>c.rev>0);
      const revM=valid.map(c=>c.ev/c.rev);
      const ebM=valid.filter(c=>c.ebitda>0).map(c=>c.ev/c.ebitda);
      const rS=getStats(revM),eS=getStats(ebM);
      const adjDRev=negEbitda?50:30;
      const adjDEb=negEbitda?50:30;
      const disc=1-adjDRev/100,discEb=1-adjDEb/100;
      setVd(p=>({...p,
        trRevLow:rS.p25*disc,trRevMid:rS.median*disc,trRevHigh:rS.p75*disc,
        trEbLow:eS.p25*discEb,trEbMid:eS.median*discEb,trEbHigh:eS.p75*discEb
      }));
    }
  },[gate]);

  // When AI comps arrive, update trading comps in vd immediately
  useEffect(()=>{
    if(!aiComps||!aiComps.length||!gate)return;
    const adjEBITDA=(gate.profitBeforeTax||0)+(gate.ownerSalary||0);
    const negEbitda=adjEBITDA<0;
    const valid=aiComps.filter(c=>c.rev>0);
    const revM=valid.map(c=>c.ev/c.rev);
    const ebM=valid.filter(c=>c.ebitda>0).map(c=>c.ev/c.ebitda);
    const rS=getStats(revM),eS=getStats(ebM);
    const adjDRev=negEbitda?50:30;
    const adjDEb=negEbitda?50:30;
    const disc=1-adjDRev/100,discEb=1-adjDEb/100;
    setVd(p=>({...p,
      trRevLow:rS.p25*disc,trRevMid:rS.median*disc,trRevHigh:rS.p75*disc,
      trEbLow:eS.p25*discEb,trEbMid:eS.median*discEb,trEbHigh:eS.p75*discEb
    }));
  },[aiComps,gate]);

  if(!gated)return <Gate onSubmit={handleGate} submitting={gateSubmitting} alreadySubmitted={alreadySubmitted}/>;

  if(!resultsReady){
    return <ResultsLoadingScreen gate={gate} compsStatus={aiCompsStatus}/>;
  }

  return(
    <div className="app-wrap results-revealed">
      <div className="main">
        <div className="page-hdr" style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",flexWrap:"wrap",gap:12}}>
          <div>
            <h1>Valuation Analysis</h1>
            <p>{gate.companyName} | {gate.sector} | {gate.geo}</p>
          </div>
        </div>
        {reportUnlocked?(
          <div style={{position:"relative"}}>
            <div data-scroll-stop><ValuationSummary gate={gate} cfg={cfg} vd={vd} unlocked={true}/></div>
            <div style={{marginTop:24}}>
              <InputsCard gate={gate} cfg={cfg}/>
              <LinkedInGateV2 gate={gate} cfg={cfg} aiComps={aiComps} onUpdate={upd} vd={vd} unlocked={true} analysis={analyzeData}/>
            </div>
            <ScrollHint/>
          </div>
        ):(
        <div style={{position:"relative",marginTop:8}}>
          <LockedPreview gate={gate} cfg={cfg} vd={vd} teaserData={analyzeData?{strengths:analyzeData.pros||[],risks:analyzeData.cons||[],insights:analyzeData.insights||[]}:null}/>
          <ScrollHint/>
          <div style={{position:"fixed",left:0,right:0,bottom:0,display:"flex",justifyContent:"center",zIndex:50,pointerEvents:"none",padding:"0 16px 24px"}}>
            <div style={{background:"#fff",border:"1px solid #e8e8e8",borderRadius:12,padding:"24px 32px",maxWidth:480,width:"100%",boxShadow:"0 -4px 24px rgba(0,9,54,0.10), 0 16px 48px rgba(0,9,54,0.22)",textAlign:"center",pointerEvents:"auto"}}>
              <div style={{display:"inline-flex",alignItems:"center",gap:6,background:"#f0fff8",border:"1px solid rgba(22,218,128,0.4)",borderRadius:8,padding:"4px 12px",fontSize:11,fontWeight:700,color:"#007a50",marginBottom:14,textTransform:"uppercase",letterSpacing:"0.5px"}}>Full Report Ready</div>
              <h2 style={{fontSize:20,fontWeight:800,color:"#000523",marginBottom:8,letterSpacing:"-0.3px",lineHeight:1.25}}>Get Your Free Valuation Report Now</h2>
              <p style={{fontSize:13,color:"#888",lineHeight:1.5,marginBottom:18}}>Your {gate.sector} business in {gate.geo} has been valued across multiple methods. Get your full report and our team will walk you through the complete analysis.</p>
              {/* No onClick unlock here, matching readiness's gate
                  (index.html's #gateOverlay): the link only opens the
                  booking page in a new tab. It used to also call
                  setReportUnlocked(true) synchronously on click — before
                  any booking was actually confirmed — which permanently
                  unblurred the full AI-generated report in this tab, visible
                  on return from the booking page. */}
              <a href="https://calendar.app.google/UfXxu6dBkZ8wjhnT6" target="_blank" rel="noopener noreferrer" style={{display:"block",width:"100%",padding:"14px",background:"#000523",color:"#fff",borderRadius:8,fontSize:15,fontWeight:700,cursor:"pointer",textDecoration:"none",fontFamily:"Inter,sans-serif",boxSizing:"border-box"}}>Get Your Free Valuation Report Now →</a>
              <div style={{fontSize:11,color:"#aaa",marginTop:9}}>Free · No commitment · Response within 24 hours</div>
            </div>
          </div>
        </div>
        )}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);

// A bad slice or a mid-file parse error can leave this page looking blank
// with no error onerror ever sees (Babel throws inside its own transpile
// pass, not as a network failure). Give the mount a few seconds, then show
// the fallback if nothing ever rendered into #root.
setTimeout(function(){
  var root=document.getElementById("root");
  if(!root||!root.firstChild){
    var fb=document.getElementById("lm-fallback");
    if(fb)fb.style.display="block";
  }
},3000);
