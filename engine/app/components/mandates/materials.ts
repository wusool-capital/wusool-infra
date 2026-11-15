import type { Material, MaterialStatus } from "../../demo/types";

const AGREEMENTS: Material["name"][] = ["Proposal", "Client NDA", "Engagement contract"];

export const isAgreement = (material: Material) => AGREEMENTS.includes(material.name);

export const inHand = (material: Material) => material.items.filter((item) => item.have).length;

export const missingFromClient = (material: Material) => material.items.filter((item) => !item.have && item.from === "client");

/** The one status move each card offers; a named person's click makes it (CLAUDE.md "AI never sends"). */
export function nextMove(material: Material): { label: string; status: MaterialStatus } | null {
  if (material.name === "Data room") return material.status === "Not started" ? { label: "Mark live", status: "Live" } : null;
  if (material.status === "Not started") return { label: "Mark drafted", status: "Drafted" };
  if (isAgreement(material)) {
    if (material.status === "Drafted") return { label: "Send for signature", status: "Sent" };
    if (material.status === "Sent") return { label: "Mark signed", status: "Signed" };
    return null;
  }
  return material.status === "Drafted" ? { label: "Approve", status: "Approved" } : null;
}

/** "CIM" and "Client NDA" read as "CIM" and "client NDA" inside a sentence. */
export const inSentence = (name: string) => name.split(" ").map((word) => (word === word.toUpperCase() ? word : word.toLowerCase())).join(" ");
