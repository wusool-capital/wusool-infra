// The model's own dimension/recommendation text is spliced into innerHTML
// below — escape it, since the prompt embeds the visitor's own free-text
// answers and the model can echo them back.
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

function renderResults(data,name,biz,sector){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.getElementById('resultsScreen').classList.add('active');
  const score=data.overallScore;
  const color=score>=75?'#C6E1EE':score>=55?'#7FB4CE':'#8FA3B8';
  document.getElementById('scoreNum').textContent=score;
  document.getElementById('scoreNum').style.color=color;
  document.getElementById('scoreCircle').style.borderColor=color;
  document.getElementById('scoreBand').textContent=data.scoreBand;
  document.getElementById('scoreBand').style.color=color;
  document.getElementById('resName').textContent=biz+' - '+sector;
  const dateStr=new Date().toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'});
  document.getElementById('resDate').textContent='Prepared for '+name+' · '+dateStr;
  document.getElementById('footerDate').textContent=dateStr;
  document.getElementById('resSummary').textContent=data.summaryParagraph;

  // Populate blurred content
  const grid=document.getElementById('dimensionsGrid');
  grid.innerHTML='';
  data.dimensions.forEach(dim=>{
    const pct=dim.score;
    const c=pct>=65?'#000523':pct>=40?'#5A93B0':'#98A2B3';
    const card=document.createElement('div');
    card.className='dim-card';
    card.innerHTML=`<div class="dim-header"><span class="dim-label">${esc(dim.name)}</span><span class="dim-score-badge" style="background:${c}20;color:${c}">${pct}</span></div><div class="dim-bar-bg"><div class="dim-bar-fill" style="width:${pct}%;background:${c}"></div></div><div class="dim-insight">${esc(dim.insight)}</div>`;
    grid.appendChild(card);
  });
  const recsEl=document.getElementById('recsContainer');
  recsEl.innerHTML='';
  data.recommendations.forEach((rec,i)=>{
    const card=document.createElement('div');
    card.className='rec-card';
    card.innerHTML=`<div class="rec-num">Priority ${i+1}</div><div class="rec-title">${esc(rec.title)}</div><div class="rec-text">${esc(rec.detail)}</div>`;
    recsEl.appendChild(card);
  });

  window.scrollTo({top:0,behavior:'smooth'});
}

function unlockReport(){
  document.getElementById('gateBlur').classList.remove('results-gate-blur');
  document.getElementById('gateOverlay').style.display='none';
  document.body.classList.remove('unlocking');
  document.body.classList.add('unlocked');
}
function startUnlock(){
  if(document.body.classList.contains('unlocking'))return;
  document.body.classList.add('unlocking');
  document.querySelectorAll('.js-unlock-cta').forEach(a=>a.textContent='Waiting for booking confirmation..');
  setTimeout(unlockReport,5000);
}
