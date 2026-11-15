// Outreach templates by type (PRD R2), shared by the Outreach tab and the
// Deal view's counterparty drawer. In production the wording comes from the outreach skill.
import type { Counterparty, Deal } from "../demo/types";

export const TEMPLATES = ["Teaser introduction", "Follow-up", "Data room invitation", "Owner approach"] as const;
export type Template = (typeof TEMPLATES)[number];

/** Templates that make sense for this row: owner approaches for seller lists, buyer templates for deals. */
export function templatesFor(row: Counterparty): Template[] {
  return row.listName ? ["Owner approach", "Follow-up"] : ["Teaser introduction", "Follow-up", "Data room invitation"];
}

// PRD MB5: before the NDA, a tracked teaser link; after it, a data room invitation for that buyer.
export function linkFor(row: Counterparty) {
  if (row.listName) return "no link";
  return row.ndaSignedDate ? "a VantageKit data room invitation" : "a tracked VantageKit teaser link";
}

export function defaultTemplate(row: Counterparty): Template {
  if (row.listName) return row.outreach ? "Follow-up" : "Owner approach";
  if (row.ndaSignedDate) return "Data room invitation";
  return row.status === "Not contacted" && !row.outreach ? "Teaser introduction" : "Follow-up";
}

export function draftBody(template: Template, row: Counterparty, deal: Deal | undefined, contactName: string) {
  const first = contactName.split(" ")[0] ?? "";
  const sign = "\n\nBest regards,\nJules";
  const whyYou = ` ${row.rationale}`;
  const nth = row.outreach?.followUpsSent === 1 ? "once more " : "";

  if (template === "Owner approach") return ownerApproachBody(contactName, row.rationale);
  if (!deal) return `Dear ${first},\n\nI am following up ${nth}on my note about a confidential conversation. Would 15 minutes this week or next work?${sign}`;

  const subject = `${deal.codeName}: ${deal.sector.toLowerCase()} in ${deal.city}`;
  if (template === "Teaser introduction")
    return `Dear ${first},\n\nWe advise on the sale of ${subject}.${whyYou} The teaser is at the link below.\n\nIf it fits, I can send the NDA so you can read the full information pack.${sign}`;
  if (template === "Follow-up")
    return `Dear ${first},\n\nI am following up ${nth}on ${deal.codeName}. The teaser is at the link below. Would a short call this week help?${sign}`;
  return `Dear ${first},\n\nThank you for signing the NDA on ${deal.codeName}. Your data room invitation is below, with the CIM and financial pack.\n\nHappy to set up a call with management once you have had a first look.${sign}`;
}

/** PRD S3: the short "open to selling?" note to an owner. Never shares deal material. */
export function ownerApproachBody(contactName: string, rationale: string) {
  const first = contactName.split(" ")[0] ?? "";
  return `Dear ${first},\n\nI work with business owners in your sector who are thinking about a sale, now or in a few years. ${rationale} Would you be open to a short, confidential call to hear what buyers pay for a business like yours today?\n\nBest regards,\nJules`;
}

/** The first sentence of a message, for the one-line context column (PRD R1). */
export function summaryOf(body: string) {
  const text = body.split("\n").filter((line) => line.trim() && !line.startsWith("Dear "))[0] ?? "";
  return text.split(". ")[0].replace(/\.$/, "") + ".";
}
