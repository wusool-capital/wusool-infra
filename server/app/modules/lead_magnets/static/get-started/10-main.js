// AED per USD, pegged — the same constant and the same direction of travel
// as benchmark's `toCalc` (30-helpers.js). The form asks in AED because that
// is what the live Tally form asks and what GCC owners think in; every
// destination downstream is USD, so the conversion happens here and nothing
// server-side converts again.
const FX = 3.6725;

function num(v){
  if(!v)return null;
  const n=parseFloat(String(v).replace(/,/g,""));
  return isNaN(n)?null:n;
}

// AED -> USD. Returns null for a blank/unparseable field so the schema's own
// `required` check reports it, rather than posting a silent 0.
function toUsd(v){
  const n=num(v);
  return n===null?null:Math.round(n/FX);
}

function clearConsentErr(){
  if(document.getElementById("consent").checked)document.getElementById("e-consent").classList.remove("show");
}

// "Other" is a real sector option (it maps to Diversified / Generalist), but
// on its own it tells the seller team nothing — so picking it reveals a free
// text box. The value is cleared on the way back out: without that, someone
// who picks Other, types, then changes their mind would post stale text
// alongside a real sector.
const sectorEl=document.getElementById("sector");
const sectorOtherWrap=document.getElementById("sector-other-wrap");
const sectorOtherEl=document.getElementById("sectorOther");

function syncSectorOther(){
  const other=sectorEl.value==="Other";
  sectorOtherWrap.hidden=!other;
  sectorOtherEl.required=other;
  if(!other)sectorOtherEl.value="";
}

sectorEl.addEventListener("change",syncSectorOther);
syncSectorOther();

async function submitGetStartedForm(e){
  e.preventDefault();
  const form=document.getElementById("get-started-form");
  const consent=document.getElementById("consent");
  document.getElementById("e-form").classList.remove("show");

  if(!consent.checked){
    document.getElementById("e-consent").classList.add("show");
    return;
  }
  document.getElementById("e-consent").classList.remove("show");

  // Native HTML5 `required` already stops the submit event before this
  // handler runs when a field is empty; this catches the rest (a number
  // field holding something unparseable).
  if(!form.checkValidity()){
    document.getElementById("e-form").classList.add("show");
    return;
  }

  const btn=document.getElementById("submit-btn");
  btn.disabled=true;
  btn.textContent="Submitting...";

  // `submission_id` is page-load scoped, not per click — see
  // ../shared/submission-id.js for why a retry has to carry the same id.
  // Keep this object literal comment-free: `test_static_contract.py`'s
  // `_payload_keys` reads the top-level keys by scanning depth and expects
  // each segment to start with the key name.
  const payload={
    submission_id:window.WUSOOL_SUBMISSION_ID,
    name:document.getElementById("name").value.trim(),
    company:document.getElementById("company").value.trim(),
    email:document.getElementById("email").value.trim(),
    geography:document.getElementById("geography").value,
    sector:sectorEl.value,
    sector_other:sectorOtherEl.value.trim()||null,
    revenue:toUsd(document.getElementById("revenue").value),
    ebitda:toUsd(document.getElementById("ebitda").value),
    years_active:num(document.getElementById("yearsActive").value),
    sell_timeline:document.getElementById("sellTimeline").value,
    domain:document.getElementById("domain").value.trim()||null,
    consent:true
  };

  try{
    const r=await fetch("/get-started",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    if(r.status===409){
      document.getElementById("e-already").classList.add("show");
      return;
    }
    if(!r.ok)throw new Error("get started failed: "+r.status);
    document.getElementById("form-wrap").classList.add("hide");
    document.getElementById("success-wrap").classList.remove("hide");
  }catch(err){
    console.warn("submit",err);
    document.getElementById("e-form").classList.add("show");
    btn.disabled=false;
    btn.textContent="Submit";
  }
}

document.getElementById("get-started-form").addEventListener("submit",submitGetStartedForm);
