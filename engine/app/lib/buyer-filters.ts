import type { BuyerRole } from "../demo/types";
import { anyOf, inRange, overlaps, readList, readRange, type Range } from "./filters";

// The Buyers search filters (PRD S1), shared by the Buyers universe and Buyers search.
export type BuyerFilterValues = { sector: string[]; geography: string[]; type: string[]; checkSize: Range; minEbitda: Range };
export type BuyerProfile = Pick<BuyerRole, "sectors" | "geographies" | "type" | "checkSizeMinUsd" | "checkSizeMaxUsd" | "ebitdaFloorUsd">;

export function readBuyerFilters(params: URLSearchParams): BuyerFilterValues {
  return {
    sector: readList(params, "sector"),
    geography: readList(params, "geography"),
    type: readList(params, "type"),
    checkSize: readRange(params, "checkSize"),
    minEbitda: readRange(params, "minEbitda"),
  };
}

export function matchesFilters(buyer: BuyerProfile, filters: BuyerFilterValues) {
  return (
    anyOf(filters.sector, buyer.sectors) &&
    anyOf(filters.geography, buyer.geographies) &&
    anyOf(filters.type, [buyer.type]) &&
    overlaps(buyer.checkSizeMinUsd, buyer.checkSizeMaxUsd, filters.checkSize) &&
    inRange(buyer.ebitdaFloorUsd, filters.minEbitda)
  );
}
