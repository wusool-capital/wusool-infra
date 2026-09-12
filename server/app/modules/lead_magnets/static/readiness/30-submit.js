async function submitForm(){
  const name=document.getElementById('cName').value.trim();
  const email=document.getElementById('cEmail').value.trim();
  const biz=document.getElementById('cBiz').value.trim();
  const sector=document.getElementById('cSector').value;
  const domain=document.getElementById('cDomain').value.trim();
  const errEl=document.getElementById('err6');
  if(!name||!email||!biz||!sector||!domain){errEl.style.display='block';setTimeout(()=>errEl.style.display='none',4000);return;}
  if(!document.getElementById('cConsent').checked){document.getElementById('errConsent').classList.add('show');return;}
  document.getElementById('errConsent').classList.remove('show');
  document.getElementById('submitBtn').disabled=true;
  const loading=document.getElementById('loadingScreen');
  loading.classList.add('active');
  let mi=0;
  const interval=setInterval(()=>{document.getElementById('loadingText').textContent=loadingMsgs[mi%loadingMsgs.length];mi++;},1100);
  const revenue=document.getElementById('cRevenue').value||null;
  const country=document.getElementById('cCountry').value||null;
  const cleanDomain=domain.replace(/^https?:\/\//,'').replace(/^www\./,'').split('/')[0].toLowerCase();

  // Field names and shape match ReadinessRequest (api/schemas.py) exactly —
  // the server builds the prompt, scores it, and records the lead in one
  // call, so this page no longer composes its own prompt or pushes to
  // Attio itself; both used to be separate fetches to dopamine-relay.
  const payload={
    submission_id:(crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`),
    name, company:biz, email, sector, revenue, country, domain:cleanDomain,
    answers:{...answers}
  };

  try{
    const r=await fetch('/readiness/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(r.status===409){
      clearInterval(interval);loading.classList.remove('active');
      document.getElementById('errAlready').style.display='block';
      return;
    }
    if(!r.ok)throw new Error('readiness score failed: '+r.status);
    const result=await r.json();
    clearInterval(interval);loading.classList.remove('active');
    renderResults(result,name,biz,sector);
  }catch(e){
    clearInterval(interval);loading.classList.remove('active');
    document.getElementById('submitBtn').disabled=false;
    alert('Something went wrong. Please try again.');console.error(e);
  }
}

