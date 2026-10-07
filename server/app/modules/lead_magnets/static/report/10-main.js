// One page serves every report; embed.js passes which one as `?slug=`.
const SLUG=new URLSearchParams(location.search).get("slug")||"";
const REPORT_URL="/reports/"+encodeURIComponent(SLUG);

// Unlock re-renders the whole report, restoring wrappers the preview cut left open.
function render(data){
  document.getElementById("report").innerHTML=data.html;
  document.getElementById("gate").classList.toggle("hide",!data.locked);
  document.getElementById("stage").classList.toggle("locked",data.locked);
  const download=document.getElementById("download-pdf");
  // aria-disabled, not disabled: the locked button must still take the click that leads to the gate.
  if(data.locked)download.setAttribute("aria-disabled","true");
  else download.removeAttribute("aria-disabled");
  document.getElementById("download").classList.remove("hide");
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
  btn.textContent="Sending code...";

  // Keep this object literal comment-free: `test_static_contract.py`'s
  // `_payload_keys` scans its top-level keys.
  const payload={
    submission_id:window.WUSOOL_SUBMISSION_ID,
    name:document.getElementById("name").value.trim(),
    email:document.getElementById("email").value.trim(),
    company:document.getElementById("company").value.trim()
  };

  try{
    await sendCode(payload);
    pendingPayload=payload;
    form.classList.add("hide");
    document.getElementById("code-email").textContent=payload.email;
    document.getElementById("code-form").classList.remove("hide");
    document.getElementById("code").focus({preventScroll:true});
  }catch(error){
    console.warn("unlock",error);
    if(error.status===422)emailErr.classList.add("show");
    else err.classList.add("show");
  }finally{
    btn.disabled=false;
    btn.textContent="Read the full report";
  }
}

// The gate form, kept for "Resend code" until the reader verifies.
let pendingPayload=null;
let challengeId=null;

async function sendCode(payload){
  const r=await fetch(REPORT_URL+"/unlock",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  if(!r.ok)throw Object.assign(new Error("unlock failed: "+r.status),{status:r.status});
  challengeId=(await r.json()).challenge_id;
}

function hideCodeErrors(){
  for(const id of ["e-code","e-expired","e-sent"])document.getElementById(id).classList.remove("show");
}

async function submitCodeForm(e){
  e.preventDefault();
  hideCodeErrors();
  const input=document.getElementById("code");
  const code=input.value.replace(/\s/g,"");
  if(!/^[0-9]{6}$/.test(code)){
    document.getElementById("e-code").classList.add("show");
    return;
  }
  const btn=document.getElementById("verify-btn");
  btn.disabled=true;
  btn.textContent="Verifying...";
  try{
    const r=await fetch(REPORT_URL+"/unlock/verify",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({challenge_id:challengeId,code:code})});
    if(r.ok){
      render(await r.json());
      return;
    }
    document.getElementById(r.status===400?"e-code":"e-expired").classList.add("show");
  }catch(error){
    console.warn("verify",error);
    document.getElementById("e-expired").classList.add("show");
  }
  btn.disabled=false;
  btn.textContent="Verify and read";
}

async function resendCode(){
  hideCodeErrors();
  const btn=document.getElementById("resend-btn");
  btn.disabled=true;
  try{
    await sendCode(pendingPayload);
    document.getElementById("code").value="";
    document.getElementById("e-sent").classList.add("show");
  }catch(error){
    console.warn("resend",error);
    document.getElementById("e-expired").classList.add("show");
  }
  btn.disabled=false;
}

function changeEmail(){
  hideCodeErrors();
  document.getElementById("code-form").classList.add("hide");
  document.getElementById("gate-form").classList.remove("hide");
  document.getElementById("email").focus({preventScroll:true});
}

function downloadPdf(e){
  if(!document.getElementById("stage").classList.contains("locked"))return;
  e.preventDefault();
  document.getElementById("gate").scrollIntoView({behavior:"smooth",block:"center"});
  document.getElementById("name").focus({preventScroll:true});
}

document.getElementById("download-pdf").href=REPORT_URL+"/pdf";
document.getElementById("download-pdf").download=SLUG+".pdf";
document.getElementById("download-pdf").addEventListener("click",downloadPdf);
document.getElementById("gate-form").addEventListener("submit",submitGateForm);
document.getElementById("code-form").addEventListener("submit",submitCodeForm);
document.getElementById("resend-btn").addEventListener("click",resendCode);
document.getElementById("change-email-btn").addEventListener("click",changeEmail);
loadReport().catch(error=>console.warn("report",error));
