// Invented comparables. "Database" rows were reviewed by an advisor and carry a source;
// "web" rows are what a web search returns when the database has fewer than 5 matches (PRD MU3, MU4).
import type { Comparable } from "./types";

const db = (row: Omit<Comparable, "verified">): Comparable => ({ ...row, verified: true });
const web = (row: Omit<Comparable, "verified" | "reviewer">): Comparable => ({ ...row, verified: false });

export const comparables: Comparable[] = [
  db({ id: "m-1", target: "Al Bayt Veterinary Group", acquirer: "Gulf Animal Health", sector: "Veterinary clinics", geography: "UAE", date: "2025-06-12", sizeUsd: 12_000_000, type: "Strategic", evEbitda: 8.4, evRevenue: 2.1, source: "Wusool deal file", reviewer: "Jules" }),
  db({ id: "m-2", target: "PetCare Riyadh", acquirer: "Oasis Growth Fund", sector: "Veterinary clinics", geography: "KSA", date: "2024-11-03", sizeUsd: 9_500_000, type: "Sponsor", evEbitda: 7.6, evRevenue: 1.8, source: "Zawya, 4 Nov 2024", reviewer: "Hugo" }),
  db({ id: "m-3", target: "Doha Pet Clinics", acquirer: "Bluewave Pet Care", sector: "Veterinary clinics", geography: "Qatar", date: "2024-03-21", sizeUsd: 6_000_000, type: "Strategic", evEbitda: 6.9, evRevenue: 1.6, source: "Company press release", reviewer: "Jules" }),
  db({ id: "m-4", target: "Muscat Vet Partners", acquirer: "Qasr Holdings", sector: "Veterinary clinics", geography: "Oman", date: "2023-09-14", sizeUsd: 4_500_000, type: "Sponsor", evEbitda: 6.2, evRevenue: 1.4, source: "MAGNiTT", reviewer: "Ramzy" }),
  db({ id: "m-5", target: "Smile Studio Jeddah", acquirer: "Smileline Group", sector: "Dental clinics", geography: "KSA", date: "2025-02-17", sizeUsd: 14_000_000, type: "Strategic", evEbitda: 9.1, evRevenue: 2.4, source: "Argaam, 18 Feb 2025", reviewer: "Jules" }),
  db({ id: "m-6", target: "Bright Dental UAE", acquirer: "Meridian Health Holdings", sector: "Dental clinics", geography: "UAE", date: "2024-07-08", sizeUsd: 22_000_000, type: "Strategic", evEbitda: 10.2, evRevenue: 2.9, source: "Wusool deal file", reviewer: "Hugo" }),
  db({ id: "m-7", target: "Ortholine Clinics", acquirer: "Orchid Dental Partners", sector: "Dental clinics", geography: "Bahrain", date: "2023-12-01", sizeUsd: 8_000_000, type: "Sponsor", evEbitda: 7.8, evRevenue: 2.0, source: "MAGNiTT", reviewer: "Ramzy" }),
  db({ id: "m-8", target: "Riyadh Smile Centre", acquirer: "Gulf Health Fund", sector: "Dental clinics", geography: "KSA", date: "2023-05-22", sizeUsd: 11_000_000, type: "Sponsor", evEbitda: 8.0, evRevenue: 2.2, source: "Zawya, 23 May 2023", reviewer: "Jules" }),
  db({ id: "m-9", target: "Pearl Dental Abu Dhabi", acquirer: "Al Noor Family Office", sector: "Dental clinics", geography: "UAE", date: "2025-09-30", sizeUsd: 6_500_000, type: "Sponsor", evEbitda: 7.2, evRevenue: 1.9, source: "Company press release", reviewer: "Hugo" }),
  db({ id: "m-10", target: "Desert Freight", acquirer: "Tidewater Capital", sector: "Logistics", geography: "UAE", date: "2025-04-11", sizeUsd: 35_000_000, type: "Sponsor", evEbitda: 6.8, evRevenue: 0.9, source: "Wusool deal file", reviewer: "Ramzy" }),
  db({ id: "m-11", target: "Coldlink KSA", acquirer: "Harbor Bridge Logistics", sector: "Logistics", geography: "KSA", date: "2024-08-19", sizeUsd: 18_000_000, type: "Strategic", evEbitda: 7.4, evRevenue: 1.1, source: "Argaam, 20 Aug 2024", reviewer: "Jules" }),
  db({ id: "m-12", target: "Gulf Last Mile", acquirer: "Saltmarsh Partners", sector: "Logistics", geography: "UAE", date: "2023-10-02", sizeUsd: 26_000_000, type: "Sponsor", evEbitda: 6.1, evRevenue: 0.8, source: "MAGNiTT", reviewer: "Ramzy" }),
  db({ id: "m-13", target: "Dammam Haulage", acquirer: "Sandcrest Freight", sector: "Logistics", geography: "KSA", date: "2025-11-01", sizeUsd: 9_000_000, type: "Strategic", evEbitda: 5.9, evRevenue: 0.7, source: "Company press release", reviewer: "Hugo" }),
  db({ id: "m-14", target: "Kuwait Express Cargo", acquirer: "Gulf Cafe Group", sector: "Logistics", geography: "Kuwait", date: "2022-06-15", sizeUsd: 12_000_000, type: "Strategic", evEbitda: 5.5, evRevenue: 0.7, source: "Zawya, 16 Jun 2022", reviewer: "Jules" }),
  db({ id: "m-15", target: "Little Stars Nurseries", acquirer: "Crestline Education Group", sector: "Education", geography: "UAE", date: "2025-01-20", sizeUsd: 16_000_000, type: "Strategic", evEbitda: 9.8, evRevenue: 2.6, source: "Wusool deal file", reviewer: "Hugo" }),
  db({ id: "m-16", target: "Bean Theory Roasters", acquirer: "Roastworks Holdings", sector: "Specialty coffee", geography: "UAE", date: "2024-05-09", sizeUsd: 7_000_000, type: "Strategic", evEbitda: 8.9, evRevenue: 1.7, source: "Company press release", reviewer: "Jules" }),
  db({ id: "m-17", target: "Sentinel Guarding", acquirer: "Tidewater Capital", sector: "Security services", geography: "UAE", date: "2025-03-03", sizeUsd: 20_000_000, type: "Sponsor", evEbitda: 6.5, evRevenue: 0.9, source: "MAGNiTT", reviewer: "Ramzy" }),

  web({ id: "w-5", target: "Happy Paws Clinics", acquirer: "Medvet Gulf Holdings", sector: "Veterinary clinics", geography: "UAE", date: "2025-10-06", sizeUsd: 7_500_000, type: "Strategic", evEbitda: 9.0, evRevenue: 2.0, source: "gulfbusiness.example/happy-paws" }),
  web({ id: "w-6", target: "VetOne Bahrain", acquirer: "Northpaw Partners", sector: "Veterinary clinics", geography: "Bahrain", date: "2024-09-15", sizeUsd: 4_000_000, type: "Sponsor", evEbitda: 6.6, evRevenue: 1.5, source: "zawya.example/vetone" }),
  web({ id: "w-1", target: "Arabica House", acquirer: "Brightline Foods", sector: "Specialty coffee", geography: "KSA", date: "2025-08-04", sizeUsd: 5_000_000, type: "Strategic", evEbitda: 9.4, evRevenue: 1.9, source: "gulfnews.example/arabica-house-deal" }),
  web({ id: "w-2", target: "Roast and Co", acquirer: "Sahar Family Holdings", sector: "Specialty coffee", geography: "Kuwait", date: "2024-02-12", sizeUsd: 3_500_000, type: "Sponsor", evEbitda: 7.7, evRevenue: 1.5, source: "arabianbusiness.example/roast-and-co" }),
  web({ id: "w-3", target: "Shield Security Services", acquirer: "Azure Peak Capital", sector: "Security services", geography: "KSA", date: "2024-10-22", sizeUsd: 15_000_000, type: "Sponsor", evEbitda: 7.1, evRevenue: 1.0, source: "zawya.example/shield-security" }),
  web({ id: "w-4", target: "Kids Campus Nurseries", acquirer: "Al Noor Family Office", sector: "Education", geography: "UAE", date: "2023-11-30", sizeUsd: 9_000_000, type: "Sponsor", evEbitda: 10.5, evRevenue: 2.8, source: "thenational.example/kids-campus" }),
];
