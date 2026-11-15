// Live twins of the demo functions: same names, inputs and return shapes. `../api.ts` picks by VITE_DATA.

// A refusal from the Toolkit throws the Kubb client's `ResponseError`.
import { addBuyer as postBuyer } from "../gen/clients/addBuyer";
import { getBuyerRole as fetchBuyer } from "../gen/clients/getBuyerRole";
import { getBuyersUniverse as fetchBuyers } from "../gen/clients/getBuyersUniverse";
import { getSellerRole as fetchSeller } from "../gen/clients/getSellerRole";
import { getCurrentUser as fetchMe } from "../gen/clients/getCurrentUser";
import { getSellersUniverse as fetchSellers } from "../gen/clients/getSellersUniverse";
import { updateBuyer as patchBuyer } from "../gen/clients/updateBuyer";
import { addSeller as postSeller } from "../gen/clients/addSeller";
import { updateSeller as patchSeller } from "../gen/clients/updateSeller";
import type { BuyerRoleView } from "../gen/types/BuyerRoleView";
import type { BuyersUniverseView } from "../gen/types/BuyersUniverseView";
import type { PersonView } from "../gen/types/PersonView";
import type { SellerRoleView } from "../gen/types/SellerRoleView";
import type { SellersUniverseView } from "../gen/types/SellersUniverseView";
import type { TeamMemberView } from "../gen/types/TeamMemberView";
import type { BuyerPatch, BuyerRole, BuyersUniverseData, Detail, NewSellerInput, Person, SellerPatch, SellerRole, SellersUniverseData, User, UserId } from "../demo/types";

// The version each row had when it was shown, so a save is refused if someone else changed it since.
const etags = new Map<string, string>();

// With no known version the header is left out, and the Toolkit answers with a message to reload.
function ifMatch(id: string) {
  const etag = etags.get(id);
  return etag ? `"${etag}"` : undefined;
}

// The Toolkit has no job titles or roles yet, so every team member counts as an advisor.
const toUser = (member: TeamMemberView): User => ({ id: member.id, name: member.name, role: "Advisor", title: "" });

const toPerson = (person: PersonView): Person => ({ ...person, title: person.title ?? undefined, email: person.email ?? undefined });

function toBuyer(row: BuyerRoleView): BuyerRole {
  etags.set(row.id, row.etag);
  return { ...row, hq: row.hq ?? "", website: row.website ?? "", notes: row.notes ?? "", type: null };
}

function toSeller(row: SellerRoleView): SellerRole {
  etags.set(row.id, row.etag);
  return { ...row, hq: row.hq ?? "", website: row.website ?? "", sector: row.sector ?? "", geography: row.geography ?? "", notes: "", estEbitdaUsd: row.estEbitdaUsd ?? undefined, reEngageDate: row.reEngageDate ?? undefined };
}

// The Toolkit takes the page's own URL params; the drawer and panel params stay in the browser.
const FILTER_KEYS = ["q", "sector", "geography", "checkSize", "minEbitda", "revenue", "ebitda", "openToSelling"] as const;
const filterParams = (params: URLSearchParams) => Object.fromEntries(FILTER_KEYS.flatMap((key) => (params.get(key) ? [[key, params.get(key)!]] : [])));

// Deals, counterparties and emails belong to later phases, so those blocks stay empty.
const later = { deals: [], counterparties: [], emails: [] };

export async function getBuyersUniverse(params: URLSearchParams, cursor?: string): Promise<BuyersUniverseData> {
  const view: BuyersUniverseView = await fetchBuyers({ query: { ...filterParams(params), cursor } }).unwrap();
  return { ...later, now: view.now, users: view.users.map(toUser), people: view.people.map(toPerson), buyers: view.buyers.map(toBuyer), matched: view.matched, total: view.total, nextCursor: view.nextCursor ?? null, options: buyerOptions(view), unavailable: view.unavailable };
}

// The edit form offers every region and country Attio allows, not only those in use.
function buyerOptions({ options }: BuyersUniverseView): BuyersUniverseData["options"] {
  const { sectors, geographies, statuses, regions, countries, hqCountries, fields } = options;
  return { sectors, geographies, statuses, geographyChoices: [...regions, ...countries].sort(), hqCountries, fields };
}

export async function getSellersUniverse(params: URLSearchParams, cursor?: string): Promise<SellersUniverseData> {
  const view: SellersUniverseView = await fetchSellers({ query: { ...filterParams(params), cursor } }).unwrap();
  return { ...later, now: view.now, users: view.users.map(toUser), people: view.people.map(toPerson), sellers: view.sellers.map(toSeller), nextCodeName: "", matched: view.matched, total: view.total, nextCursor: view.nextCursor ?? null, options: view.options, unavailable: view.unavailable };
}

/** The Toolkit records the signed-in person from their Access token, so `userId` is not sent. */
export async function addBuyer(_userId: UserId, fields: Required<BuyerPatch> & Pick<BuyerRole, "name" | "hq" | "website">) {
  const [sector] = fields.sectors;
  const created = await postBuyer({
    body: {
      name: fields.name,
      website: fields.website,
      hq: fields.hq || null,
      sector,
      status: fields.status,
      notes: fields.notes || null,
      checkSizeMinUsd: fields.checkSizeMinUsd,
      checkSizeMaxUsd: fields.checkSizeMaxUsd,
      ebitdaFloorUsd: fields.ebitdaFloorUsd,
      geographies: fields.geographies,
      details: fields.details,
    },
  }).unwrap();
  etags.set(created.id, created.etag);
}

// The values of the extra Slack fields come with the single-role read, not with the lists.
export async function getBuyerDetails(id: string): Promise<Detail[]> {
  return (await fetchBuyer({ path: { role_id: id } }).unwrap()).details ?? [];
}

export async function getSellerDetails(id: string): Promise<Detail[]> {
  return (await fetchSeller({ path: { role_id: id } }).unwrap()).details ?? [];
}

export async function addSeller(_userId: UserId, fields: NewSellerInput) {
  const created = await postSeller({
    body: {
      name: fields.name,
      website: fields.website,
      hq: fields.hq || null,
      sector: fields.sector,
      openToSelling: fields.openToSelling,
      estRevenueUsd: fields.estRevenueUsd,
      estEbitdaUsd: fields.estEbitdaUsd ?? null,
      reEngageDate: fields.reEngageDate || null,
      details: fields.details,
    },
  }).unwrap();
  etags.set(created.id, created.etag);
}

export async function updateBuyer(_userId: UserId, id: string, patch: BuyerPatch) {
  const updated = await patchBuyer({
    path: { role_id: id },
    headers: { "if-match": ifMatch(id) },
    // Type, owner and sectors have no write path; the drawer locks them.
    body: {
      ...("status" in patch && { status: patch.status }),
      ...("notes" in patch && { notes: patch.notes }),
      ...("checkSizeMinUsd" in patch && { checkSizeMinUsd: patch.checkSizeMinUsd }),
      ...("checkSizeMaxUsd" in patch && { checkSizeMaxUsd: patch.checkSizeMaxUsd }),
      ...("ebitdaFloorUsd" in patch && { ebitdaFloorUsd: patch.ebitdaFloorUsd }),
      ...("geographies" in patch && { geographies: patch.geographies }),
      ...(patch.details?.length && { details: patch.details }),
    },
  }).unwrap();
  etags.set(updated.id, updated.etag);
}

export async function updateSeller(_userId: UserId, id: string, patch: SellerPatch) {
  const updated = await patchSeller({
    path: { role_id: id },
    headers: { "if-match": ifMatch(id) },
    body: {
      ...("estRevenueUsd" in patch && { estRevenueUsd: patch.estRevenueUsd }),
      ...("estEbitdaUsd" in patch && { estEbitdaUsd: patch.estEbitdaUsd }),
      ...("openToSelling" in patch && { openToSelling: patch.openToSelling }),
      ...("reEngageDate" in patch && { reEngageDate: patch.reEngageDate ?? null }),
      ...(patch.details?.length && { details: patch.details }),
    },
  }).unwrap();
  etags.set(updated.id, updated.etag);
}

export async function getCurrentUser(): Promise<User> {
  const me = await fetchMe().unwrap();
  return { id: me.id, name: me.name, role: "Advisor", title: "" };
}
