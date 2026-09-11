function goTo(n){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.getElementById('resultsScreen').classList.remove('active');
  currentSection=n;
  if(n>=1&&n<=6)document.getElementById('sec'+n).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}



function selectOpt(btn){
  const g=btn.closest('.options');
  g.querySelectorAll('.option-btn').forEach(b=>b.classList.remove('selected'));
  btn.classList.add('selected');
  answers[g.getAttribute('data-q')]=parseFloat(btn.getAttribute('data-val'));
}

function nextSection(from,to){
  const required=sectionQuestions[from]||[];
  const errEl=document.getElementById('err'+from);
  if(from===5){
    const t14=document.getElementById('q14').value.trim();
    const t15=document.getElementById('q15').value.trim();
    if(!t14||!t15||required.some(q=>answers[q]===undefined)){errEl.style.display='block';setTimeout(()=>errEl.style.display='none',3000);return;}
    answers['q14']=t14;answers['q15']=t15;
  } else {
    if(required.some(q=>answers[q]===undefined)){errEl.style.display='block';setTimeout(()=>errEl.style.display='none',3000);return;}
  }
  errEl.style.display='none';goTo(to);
}

function clearConsentErr(){
  if(document.getElementById('cConsent').checked)document.getElementById('errConsent').classList.remove('show');
}

