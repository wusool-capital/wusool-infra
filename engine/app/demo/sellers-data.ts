// Invented demo data for the Sellers universe: Attio seller_roles entries. Lumen, Brightsmile
// and Kiteway are also on seller lists in Outreach; Sandcrest and Northstar are Project Atlas targets.
import type { Person, SellerRole } from "./types";

export const sellerPeople: Person[] = [
  { id: "p-wael", name: "Wael Hamdan", org: "Brightsmile Ortho", role: "other", title: "Founder" },
  { id: "p-mona", name: "Mona Al Sayegh", org: "Little Oaks Nurseries", role: "other", title: "Owner" },
  { id: "p-tariq", name: "Tariq Bashir", org: "Bayside Pet Clinic", role: "other", title: "Owner and head vet" },
  { id: "p-ghada", name: "Ghada Fakhoury", org: "Saffa Bakeries", role: "other", title: "Managing partner" },
  { id: "p-hisham", name: "Hisham Qureshi", org: "Clearwave Facility Services", role: "other", title: "Founder and CEO" },
  { id: "p-rasha", name: "Rasha Nasser", org: "Medline Diagnostics", role: "other", title: "Owner" },
];

export const sellerRoles: SellerRole[] = [
  { id: "s-lumen", name: "Lumen Dental Clinics", hq: "Jeddah", website: "lumendental.example", sector: "Dental", geography: "KSA", estRevenueUsd: 6_000_000, estEbitdaUsd: 1_500_000, openToSelling: "Interested", reEngageDate: "2026-11-18", ownerId: "jules", contactIds: ["p-fahad"], notes: "Five clinics, founder in his sixties with no successor." },
  { id: "s-brightsmile", name: "Brightsmile Ortho", hq: "Riyadh", website: "brightsmile.example", sector: "Dental", geography: "KSA", estRevenueUsd: 2_500_000, estEbitdaUsd: 600_000, openToSelling: "Unknown", ownerId: "jules", contactIds: ["p-wael"], notes: "Orthodontics group with three branches." },
  { id: "s-kiteway", name: "Kiteway Logistics", hq: "Dammam", website: "kiteway.example", sector: "Logistics", geography: "KSA", estRevenueUsd: 8_000_000, estEbitdaUsd: 1_100_000, openToSelling: "Warm intro", reEngageDate: "2026-11-16", ownerId: "jules", contactIds: ["p-saad"], notes: "Cold-chain trucking, 60 vehicles." },
  { id: "s-sandcrest", name: "Sandcrest Freight", hq: "Dammam", website: "sandcrest.example", sector: "Logistics", geography: "KSA", estRevenueUsd: 11_000_000, estEbitdaUsd: 1_900_000, openToSelling: "Warm intro", ownerId: "jules", contactIds: ["p-faisal"], notes: "Freight forwarder with a bonded warehouse. In LOI talks on Project Atlas." },
  { id: "s-northstar", name: "Northstar Logistics", hq: "Riyadh", website: "northstarlog.example", sector: "Logistics", geography: "KSA", estRevenueUsd: 5_000_000, estEbitdaUsd: 700_000, openToSelling: "Interested", ownerId: "jules", contactIds: ["p-rami"], notes: "Last-mile operator in Riyadh, owner open to a sale." },
  { id: "s-littleoaks", name: "Little Oaks Nurseries", hq: "Dubai", website: "littleoaks.example", sector: "Education", geography: "UAE", estRevenueUsd: 4_000_000, estEbitdaUsd: 900_000, openToSelling: "Unknown", ownerId: "hugo", contactIds: ["p-mona"], notes: "Four nurseries in Dubai, full waiting lists." },
  { id: "s-bayside", name: "Bayside Pet Clinic", hq: "Abu Dhabi", website: "baysidepet.example", sector: "Veterinary", geography: "UAE", estRevenueUsd: 2_000_000, estEbitdaUsd: 400_000, openToSelling: "Interested", reEngageDate: "2026-12-01", ownerId: "jules", contactIds: ["p-tariq"], notes: "Two clinics; owner asked to talk again after the busy season." },
  { id: "s-saffa", name: "Saffa Bakeries", hq: "Sharjah", website: "saffabakeries.example", sector: "Food and beverage", geography: "UAE", estRevenueUsd: 7_000_000, estEbitdaUsd: 1_100_000, openToSelling: "Unknown", ownerId: "ramzy", contactIds: ["p-ghada"], notes: "Wholesale bakery supplying 300 grocery stores." },
  { id: "s-clearwave", name: "Clearwave Facility Services", hq: "Doha", website: "clearwavefm.example", sector: "Business services", geography: "Qatar", estRevenueUsd: 15_000_000, estEbitdaUsd: 2_200_000, openToSelling: "Warm intro", ownerId: "ramzy", contactIds: ["p-hisham"], notes: "Cleaning and maintenance contracts with hospitals and malls." },
  { id: "s-medline", name: "Medline Diagnostics", hq: "Manama", website: "medlinediag.example", sector: "Healthcare", geography: "Bahrain", estRevenueUsd: 3_500_000, estEbitdaUsd: 700_000, openToSelling: "Unknown", ownerId: "hugo", contactIds: ["p-rasha"], notes: "Three diagnostic labs with insurer contracts." },
  { id: "s-greenpath", name: "Greenpath Landscaping", hq: "Muscat", website: "greenpath.example", sector: "Business services", geography: "Oman", estRevenueUsd: 2_000_000, estEbitdaUsd: 300_000, openToSelling: "Unknown", ownerId: "hugo", contactIds: [], notes: "Owner contact not found yet." },
  { id: "s-alwaha", name: "Al Waha Schools", hq: "Kuwait City", website: "alwahaschools.example", sector: "Education", geography: "Kuwait", estRevenueUsd: 19_000_000, estEbitdaUsd: 3_900_000, openToSelling: "Interested", reEngageDate: "2026-11-12", ownerId: "ramzy", contactIds: [], notes: "Two K-12 schools; family discussing succession." },
];
