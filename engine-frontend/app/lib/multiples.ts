import type { Comparable } from "../demo/types";
import { anyOf, inRange, readList, readRange, writeRange, type Range } from "./filters";

export const MULTIPLES = ["EV/EBITDA", "EV/Revenue"] as const;
export type Multiple = (typeof MULTIPLES)[number];

export type MultipleFilters = { sector: string[]; geography: string[]; size: Range; year: string[]; type: string[]; multiple: Multiple };

export function readMultipleFilters(params: URLSearchParams): MultipleFilters {
  return {
    sector: readList(params, "sector"),
    geography: readList(params, "geography"),
    size: readRange(params, "size"),
    year: readList(params, "year"),
    type: readList(params, "type"),
    multiple: params.get("multiple") === "EV/Revenue" ? "EV/Revenue" : "EV/EBITDA",
  };
}

export function matchesMultipleFilters(row: Comparable, filters: MultipleFilters) {
  return (
    anyOf(filters.sector, [row.sector]) &&
    anyOf(filters.geography, [row.geography]) &&
    inRange(row.sizeUsd, filters.size) &&
    anyOf(filters.year, [row.date.slice(0, 4)]) &&
    anyOf(filters.type, [row.type])
  );
}

export function multipleOf(row: Comparable, multiple: Multiple) {
  return multiple === "EV/EBITDA" ? row.evEbitda : row.evRevenue;
}

/** "7.4x" */
export function formatMultiple(value: number) {
  return `${value.toFixed(1)}x`;
}

export function median(values: number[]) {
  if (values.length === 0) return undefined;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

// PRD MU2. Once live, the smallest model tier reads the question and returns these same filters;
// the demo uses word rules. Either way the user sees the filters before any result runs.
const SECTOR_WORDS: [RegExp, string][] = [
  [/\bvet|veterinar|animal/i, "Veterinary clinics"],
  [/dental|dentist|ortho/i, "Dental clinics"],
  [/logistic|freight|cold.?chain|haulage|cargo/i, "Logistics"],
  [/nurser|school|education/i, "Education"],
  [/coffee|roast/i, "Specialty coffee"],
  [/security|guard/i, "Security services"],
];
const PLACE_WORDS: [RegExp, string][] = [
  [/\buae\b|dubai|abu dhabi|sharjah/i, "UAE"],
  [/\bksa\b|saudi|riyadh|jeddah/i, "KSA"],
  [/qatar|doha/i, "Qatar"],
  [/kuwait/i, "Kuwait"],
  [/oman|muscat/i, "Oman"],
  [/bahrain|manama/i, "Bahrain"],
];

export function filtersFromQuestion(question: string, thisYear: number) {
  const params = new URLSearchParams();
  const sectors = SECTOR_WORDS.filter(([pattern]) => pattern.test(question)).map(([, sector]) => sector);
  if (sectors.length) params.set("sector", sectors.join(","));
  // "GCC" means every country, so no geography filter.
  const places = /\bgcc\b/i.test(question) ? [] : PLACE_WORDS.filter(([pattern]) => pattern.test(question)).map(([, place]) => place);
  if (places.length) params.set("geography", places.join(","));
  const under = question.match(/(?:under|below|less than)\s*\$?(\d+(?:\.\d+)?)\s*m/i);
  const over = question.match(/(?:over|above|more than)\s*\$?(\d+(?:\.\d+)?)\s*m/i);
  const size = writeRange({ min: over ? Number(over[1]) * 1_000_000 : undefined, max: under ? Number(under[1]) * 1_000_000 : undefined });
  if (size) params.set("size", size);
  const lastYears = question.match(/last\s+(\d+)\s+years?/i);
  if (lastYears) params.set("year", Array.from({ length: Number(lastYears[1]) }, (_, index) => String(thisYear - index)).join(","));
  if (/sponsor|private equity|\bpe\b|fund/i.test(question)) params.set("type", "Sponsor");
  else if (/strategic/i.test(question)) params.set("type", "Strategic");
  params.set("multiple", /revenue|sales/i.test(question) ? "EV/Revenue" : "EV/EBITDA");
  return params;
}
