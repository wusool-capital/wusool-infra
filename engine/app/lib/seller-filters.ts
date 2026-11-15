import type { SellerRole } from "../demo/types";
import { anyOf, inRange, readList, readRange, type Range } from "./filters";

export type SellerFilterValues = { sector: string[]; geography: string[]; revenue: Range; ebitda: Range; openToSelling: string[] };

export function readSellerFilters(params: URLSearchParams): SellerFilterValues {
  return {
    sector: readList(params, "sector"),
    geography: readList(params, "geography"),
    revenue: readRange(params, "revenue"),
    ebitda: readRange(params, "ebitda"),
    openToSelling: readList(params, "openToSelling"),
  };
}

export function matchesSellerFilters(seller: SellerRole, filters: SellerFilterValues) {
  return (
    anyOf(filters.sector, [seller.sector]) &&
    anyOf(filters.geography, [seller.geography]) &&
    inRange(seller.estRevenueUsd, filters.revenue) &&
    inRange(seller.estEbitdaUsd, filters.ebitda) &&
    anyOf(filters.openToSelling, [seller.openToSelling])
  );
}
