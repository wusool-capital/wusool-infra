// The one next thing to do on a deal, from its own records, by rule (no AI): a buyer follow-up
// that is due, then an offer waiting for review, then the first unfinished document in deal order,
// then the deal's written next step. Each points at the Deal view panel where it is done.
import { inSentence, isAgreement } from "../components/mandates/materials";
import type { Counterparty, Deal, Material, Offer } from "../demo/types";
import { formatDate } from "./format";
import { followUp } from "./follow-ups";

export type NextAction = { label: string; reason: string; to: string };

const DONE: Material["status"][] = ["Signed", "Approved", "Live"];

function materialLabel(material: Material) {
  const name = inSentence(material.name);
  if (material.name === "Data room") return "Set up the data room";
  if (material.status === "Not started") return material.name === "Financials" ? "Prepare the financials" : `Draft the ${name}`;
  if (!isAgreement(material)) return `Approve the ${name}`;
  return material.status === "Drafted" ? `Send the ${name} for signature` : `Get the ${name} signed`;
}

export function nextAction(deal: Deal, records: { counterparties: Counterparty[]; materials: Material[]; offers: Offer[] }, now: string): NextAction {
  const page = `/deals/${deal.id}`;
  const today = now.slice(0, 10);

  const dueFollowUp = records.counterparties
    .map((row) => ({ row, step: followUp(row) }))
    .filter(({ step }) => step.state === "due" && step.date <= today)
    .sort((a, b) => (a.step.state === "due" && b.step.state === "due" ? a.step.date.localeCompare(b.step.date) : 0))[0];
  if (dueFollowUp && dueFollowUp.step.state === "due") {
    const when = dueFollowUp.step.date === today ? "due today" : `was due ${formatDate(dueFollowUp.step.date)}`;
    return { label: `Follow up with ${dueFollowUp.row.name}`, reason: `Follow-up ${when}.`, to: `${page}?panel=buyer:${dueFollowUp.row.id}` };
  }

  const newOffer = records.offers.find((offer) => offer.status === "Received");
  if (newOffer) {
    const buyer = records.counterparties.find((row) => row.id === newOffer.counterpartyId);
    return { label: `Review the offer from ${buyer?.name ?? "the buyer"}`, reason: `${newOffer.type} received ${formatDate(newOffer.date)}.`, to: `${page}?tab=offers&panel=offer:${newOffer.id}` };
  }

  const openDocument = records.materials.find((material) => !DONE.includes(material.status));
  if (openDocument) {
    const missing = openDocument.items.filter((item) => !item.have).length;
    return {
      label: materialLabel(openDocument),
      reason: missing ? `${missing} of ${openDocument.items.length} items still missing.` : "Every item is in hand.",
      to: `${page}?tab=materials&panel=material:${openDocument.id}`,
    };
  }

  return { label: "Open Deal view", reason: deal.nextStep, to: page };
}
