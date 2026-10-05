// One page serves every report; embed.js passes which one as `?slug=`.
const SLUG=new URLSearchParams(location.search).get("slug")||"";
const REPORT_URL="/reports/"+encodeURIComponent(SLUG);

// Unlock re-renders the whole report, restoring wrappers the preview cut left open.
function render(data){
  document.getElementById("report").innerHTML=data.html;
  document.getElementById("gate").classList.toggle("hide",!data.locked);
  document.getElementById("stage").classList.toggle("locked",data.locked);
  fit();
}

// Fixed-width exports (A4 is 794px) scale to fill the frame, up or down; reflowing HTML stays 1:1.
function fit(){
  const report=document.getElementById("report");
  report.style.zoom="";
  report.style.width="min-content";
  const narrowest=report.scrollWidth;
  report.style.width="max-content";
  const widest=report.scrollWidth;
  report.style.width="";
  const available=document.documentElement.clientWidth;
  let scale=1;
  if(widest<=available)scale=available/widest;
  else if(narrowest>available)scale=available/narrowest;
  report.style.zoom=String(scale);
}
window.addEventListener("resize",fit);

async function loadReport(){
  // A missing report renders nothing, so the iframe stays at zero height.
  const r=await fetch(REPORT_URL,{credentials:"same-origin"});
  if(!r.ok)return;
  render(await r.json());
}

async function submitGateForm(e){
  e.preventDefault();
  const form=document.getElementById("gate-form");
  const err=document.getElementById("e-form");
  const emailErr=document.getElementById("e-email");
  err.classList.remove("show");
  emailErr.classList.remove("show");
  if(!document.getElementById("email").checkValidity()){
    emailErr.classList.add("show");
    return;
  }
  if(!form.checkValidity()){
    err.classList.add("show");
    return;
  }

  const btn=document.getElementById("submit-btn");
  btn.disabled=true;
  btn.textContent="Opening...";

  // Keep this object literal comment-free: `test_static_contract.py`'s
  // `_payload_keys` scans its top-level keys.
  const payload={
    submission_id:window.WUSOOL_SUBMISSION_ID,
    name:document.getElementById("name").value.trim(),
    email:document.getElementById("email").value.trim(),
    company:document.getElementById("company").value.trim()
  };

  try{
    const r=await fetch(REPORT_URL+"/unlock",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    if(r.status===422){
      emailErr.classList.add("show");
      btn.disabled=false;
      btn.textContent="Read the full report";
      return;
    }
    if(!r.ok)throw new Error("unlock failed: "+r.status);
    render(await r.json());
  }catch(error){
    console.warn("unlock",error);
    err.classList.add("show");
    btn.disabled=false;
    btn.textContent="Read the full report";
  }
}

document.getElementById("gate-form").addEventListener("submit",submitGateForm);
loadReport().catch(error=>console.warn("report",error));
