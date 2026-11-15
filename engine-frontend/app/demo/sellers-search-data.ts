// Invented companies that Toolkit discovery and Apollo company search return in the demo.
// Lumen and Kiteway share a domain with Attio seller roles, so they show as "In Attio".
import type { SellerCandidate } from "./types";

// A getter, so each company gets its own contact list (a shared [] would leak contacts across rows).
const base = () => ({ contactIds: [], enriched: false });

export const sellerCandidates: SellerCandidate[] = [
  { ...base(), id: "q-lumen", name: "Lumen Dental Clinics", hq: "Jeddah", website: "lumendental.example", sector: "Dental", geography: "KSA", estRevenueUsd: 6_000_000, employees: 85, source: "Wusool database", rationale: "Five clinics, founder in his sixties with no successor." },
  { ...base(), id: "q-kiteway", name: "Kiteway Logistics", hq: "Dammam", website: "kiteway.example", sector: "Logistics", geography: "KSA", estRevenueUsd: 8_500_000, employees: 140, source: "Apollo", rationale: "Cold-chain trucking, 60 vehicles." },
  { ...base(), id: "q-pearlsmile", name: "Pearlsmile Dental Studio", hq: "Riyadh", website: "pearlsmile.example", sector: "Dental", geography: "KSA", estRevenueUsd: 3_500_000, employees: 40, source: "Apollo", rationale: "Two cosmetic dentistry clinics, same owner for 18 years." },
  { ...base(), id: "q-alnakheel", name: "Al Nakheel Dental Centre", hq: "Dammam", website: "alnakheeldental.example", sector: "Dental", geography: "KSA", estRevenueUsd: 5_000_000, employees: 62, source: "Wusool database", rationale: "Three branches; owner stepped back from daily work in 2025." },
  { ...base(), id: "q-vetcare", name: "VetCare Sharjah", hq: "Sharjah", website: "vetcaresharjah.example", sector: "Veterinary", geography: "UAE", estRevenueUsd: 2_500_000, employees: 28, source: "Apollo", rationale: "Single clinic with boarding; owner is the head vet." },
  { ...base(), id: "q-paws", name: "Paws and Claws Clinics", hq: "Dubai", website: "pawsclaws.example", sector: "Veterinary", geography: "UAE", estRevenueUsd: 4_000_000, employees: 45, source: "Wusool database", rationale: "Three clinics in Dubai; founders are both over 60." },
  { ...base(), id: "q-swiftcold", name: "SwiftCold Transport", hq: "Riyadh", website: "swiftcold.example", sector: "Logistics", geography: "KSA", estRevenueUsd: 12_000_000, employees: 210, source: "Apollo", rationale: "Refrigerated fleet serving grocery chains." },
  { ...base(), id: "q-gulfbridge", name: "Gulfbridge Freight", hq: "Jebel Ali", website: "gulfbridge.example", sector: "Logistics", geography: "UAE", estRevenueUsd: 18_000_000, employees: 160, source: "Apollo", rationale: "Freight forwarder with a free-zone warehouse." },
  { ...base(), id: "q-bright", name: "Bright Minds Nursery", hq: "Abu Dhabi", website: "brightminds.example", sector: "Education", geography: "UAE", estRevenueUsd: 3_000_000, employees: 55, source: "Wusool database", rationale: "Two nurseries with waiting lists; owner relocating abroad." },
  { ...base(), id: "q-oven", name: "Stone Oven Bakery", hq: "Kuwait City", website: "stoneoven.example", sector: "Food and beverage", geography: "Kuwait", estRevenueUsd: 7_000_000, employees: 120, source: "Apollo", rationale: "Wholesale bakery supplying hotels and cafes." },
  { ...base(), id: "q-sparkle", name: "Sparkle Facility Care", hq: "Doha", website: "sparklefc.example", sector: "Business services", geography: "Qatar", estRevenueUsd: 9_000_000, employees: 380, source: "Wusool database", rationale: "Cleaning contracts with schools and offices." },
  { ...base(), id: "q-labline", name: "Labline Diagnostics", hq: "Muscat", website: "labline.example", sector: "Healthcare", geography: "Oman", estRevenueUsd: 4_500_000, employees: 70, source: "Apollo", rationale: "Two labs with insurer contracts; family-owned." },
];
