function renderResults(data,name,biz,sector){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.getElementById('resultsScreen').classList.add('active');
  const score=data.overallScore;
  const color=score>=75?'#16DA80':score>=55?'#f5a623':'#DC2626';
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
    const c=pct>=65?'#16DA80':pct>=40?'#f5a623':'#DC2626';
    const card=document.createElement('div');
    card.className='dim-card';
    card.innerHTML=`<div class="dim-header"><span class="dim-label">${dim.name}</span><span class="dim-score-badge" style="background:${c}20;color:${c}">${pct}</span></div><div class="dim-bar-bg"><div class="dim-bar-fill" style="width:${pct}%;background:${c}"></div></div><div class="dim-insight">${dim.insight}</div>`;
    grid.appendChild(card);
  });
  const recsEl=document.getElementById('recsContainer');
  recsEl.innerHTML='';
  data.recommendations.forEach((rec,i)=>{
    const card=document.createElement('div');
    card.className='rec-card';
    card.innerHTML=`<div class="rec-num">Priority ${i+1}</div><div class="rec-title">${rec.title}</div><div class="rec-text">${rec.detail}</div>`;
    recsEl.appendChild(card);
  });

  window.scrollTo({top:0,behavior:'smooth'});
}
