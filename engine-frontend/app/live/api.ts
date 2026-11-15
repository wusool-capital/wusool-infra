// The Toolkit-backed versions of the Phase 1 functions. Each keeps the name, inputs and
// return shape of its demo twin in `../demo/api.ts`; `../api.ts` picks one by VITE_DATA.
// Calls go through the Kubb client in `../gen` and throw a `ResponseError` on a refusal.
import { addBuyer as postBuyer } from "../gen/clients/addBuyer";
import { getBuyersUniverse as fetchBuyers } from "../gen/clients/getBuyersUniverse";
import { getCurrentUser as fetchMe } from "../gen/clients/getCurrentUser";
import { getSellersUniverse as fetchSellers } from "../gen/clients/getSellersUniverse";
import { updateBuyer as patchBuyer } from "../gen/clients/updateBuyer";
import { updateSeller as patchSeller } from "../gen/clients/updateSeller";
import type { BuyerRoleView } from "../gen/types/BuyerRoleView";
import type { BuyersUniverseView } from "../gen/types/BuyersUniverseView";
import type { PersonView } from "../gen/types/PersonView";
import type { SellerRoleView } from "../gen/types/SellerRoleView";
import type { SellersUniverseView } from "../gen/types/SellersUniverseView";
import type { TeamMemberView } from "../gen/types/TeamMemberView";
import type { BuyerPatch, BuyerRole, BuyersUniverseData, Person, SellerPatch, SellerRole, SellersUniverseData, User, UserId } from "../demo/types";

// The version each row had when it was shown, so a save is refused if someone else changed it since.
const etags = new Map<string, string>();

function ifMatch(id: string) {
  const etag = etags.get(id);
  if (!etag) throw new Error(`Reload the page: no version is known for ${id}`);
  return `"${etag}"`;
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
  return { ...later, now: view.now, users: view.users.map(toUser), people: view.people.map(toPerson), buyers: view.buyers.map(toBuyer), matched: view.matched, total: view.total, nextCursor: view.nextCursor ?? null, options: view.options, unavailable: view.unavailable };
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
    },
  }).unwrap();
  etags.set(created.id, created.etag);
}

export async function updateBuyer(_userId: UserId, id: string, patch: BuyerPatch) {
  const updated = await patchBuyer({
    path: { role_id: id },
    headers: { "if-match": ifMatch(id) },
    // Only status, notes and the money fields have a write path; the drawer locks the rest.
    body: {
      ...("status" in patch && { status: patch.status }),
      ...("notes" in patch && { notes: patch.notes }),
      ...("checkSizeMinUsd" in patch && { checkSizeMinUsd: patch.checkSizeMinUsd }),
      ...("checkSizeMaxUsd" in patch && { checkSizeMaxUsd: patch.checkSizeMaxUsd }),
      ...("ebitdaFloorUsd" in patch && { ebitdaFloorUsd: patch.ebitdaFloorUsd }),
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
    },
  }).unwrap();
  etags.set(updated.id, updated.etag);
}

export async function getCurrentUser(): Promise<User> {
  const me = await fetchMe().unwrap();
  return { id: me.id, name: me.name, role: "Advisor", title: "" };
}
