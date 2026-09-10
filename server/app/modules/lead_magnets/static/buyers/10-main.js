function clearConsentErr(){
  if(document.getElementById("consent").checked)document.getElementById("e-consent").classList.remove("show");
}

function selectedValues(select){
  return [...select.selectedOptions].map(o=>o.value);
}

function num(v){
  if(!v)return null;
  const n=parseFloat(String(v).replace(/,/g,""));
  return isNaN(n)?null:n;
}

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

  // Native HTML5 `required` on the text inputs and multi-selects already
  // stops the submit event before this handler runs when one is empty —
  // this is a defensive second check, not the primary validation.
  if(!form.checkValidity()){
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
    org_type:selectedValues(document.getElementById("orgType")),
    target_geography:selectedValues(document.getElementById("targetGeography")),
    sector_focus:selectedValues(document.getElementById("sectorFocus")),
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
