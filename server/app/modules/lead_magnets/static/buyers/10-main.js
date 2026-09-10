function clearConsentErr(){
  if(document.getElementById("consent").checked)document.getElementById("e-consent").classList.remove("show");
}

// Click-to-toggle, searchable multiselect. Plain divs instead of a native
// <select multiple> — a native one needs ctrl/cmd+click to pick more than
// one option, which is not discoverable and not what a visitor expects
// from a web form.
function initMultiSelect(containerId){
  const container=document.getElementById(containerId);
  const search=container.querySelector(".ms-search");
  const opts=[...container.querySelectorAll(".ms-opt")];
  const empty=container.querySelector(".ms-empty");
  const selected=new Set();

  const toggle=opt=>{
    const v=opt.getAttribute("data-value");
    if(selected.has(v)){selected.delete(v);opt.classList.remove("selected");}
    else{selected.add(v);opt.classList.add("selected");}
    opt.setAttribute("aria-selected",selected.has(v)?"true":"false");
  };

  opts.forEach(opt=>{
    opt.setAttribute("aria-selected","false");
    opt.addEventListener("click",()=>toggle(opt));
    opt.addEventListener("keydown",e=>{
      if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle(opt);}
    });
  });

  search.addEventListener("input",()=>{
    const q=search.value.trim().toLowerCase();
    let anyVisible=false;
    opts.forEach(opt=>{
      const match=!q||opt.textContent.toLowerCase().includes(q);
      opt.classList.toggle("ms-hidden",!match);
      if(match)anyVisible=true;
    });
    if(empty)empty.classList.toggle("hide",anyVisible);
  });

  return {hasSelection:()=>selected.size>0, values:()=>[...selected]};
}

function num(v){
  if(!v)return null;
  const n=parseFloat(String(v).replace(/,/g,""));
  return isNaN(n)?null:n;
}

const orgTypeMS=initMultiSelect("orgType");
const targetGeographyMS=initMultiSelect("targetGeography");
const sectorFocusMS=initMultiSelect("sectorFocus");

async function submitBuyerForm(e){
  e.preventDefault();
  const form=document.getElementById("buyer-form");
  const consent=document.getElementById("consent");
  document.getElementById("e-form").classList.remove("show");

  if(!consent.checked){
    document.getElementById("e-consent").classList.add("show");
    return;
  }
  document.getElementById("e-consent").classList.remove("show");

  // Native HTML5 `required` on the text inputs still stops the submit
  // event before this handler runs when one is empty. The three
  // multiselects are plain divs now, not a native <select required>, so
  // their own "at least one picked" check has to happen here.
  const multiSelectsFilled=orgTypeMS.hasSelection()&&targetGeographyMS.hasSelection()&&sectorFocusMS.hasSelection();
  if(!form.checkValidity()||!multiSelectsFilled){
    document.getElementById("e-form").classList.add("show");
    return;
  }

  const btn=document.getElementById("submit-btn");
  btn.disabled=true;
  btn.textContent="Submitting...";

  const payload={
    submission_id:(crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`),
    full_name:document.getElementById("fullName").value.trim(),
    org_name:document.getElementById("orgName").value.trim(),
    email:document.getElementById("email").value.trim(),
    org_type:orgTypeMS.values(),
    target_geography:targetGeographyMS.values(),
    sector_focus:sectorFocusMS.values(),
    check_size_min:num(document.getElementById("checkSizeMin").value),
    check_size_max:num(document.getElementById("checkSizeMax").value),
    prior_gcc_acquisition:document.getElementById("priorAcquisition").value.trim()||null,
    linkedin_url:document.getElementById("linkedin").value.trim()||null,
    domain:document.getElementById("domain").value.trim()||null,
    consent:true
  };

  try{
    const r=await fetch("/buyer/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    if(!r.ok)throw new Error("buyer apply failed: "+r.status);
    document.getElementById("form-wrap").classList.add("hide");
    document.getElementById("success-wrap").classList.remove("hide");
  }catch(err){
    console.warn("submit",err);
    document.getElementById("e-form").classList.add("show");
    btn.disabled=false;
    btn.textContent="Join the Buyer Network";
  }
}

document.getElementById("buyer-form").addEventListener("submit",submitBuyerForm);
