// Filter values as they live in the URL, so a filtered view can be shared or bookmarked.
// Lists are comma-separated ("Dental,Veterinary"); ranges are in $M ("10-40", "10-", "-40").

/** A plain string is both value and label; owners use { value: "jules", label: "Jules" }. */
export type FilterOption = string | { value: string; label: string };
export type ListFilter = {
  kind: "list";
  key: string;
  label: string;
  options: FilterOption[];
  /** Used while the URL has no value, such as "my deals" on Pipeline. An empty value then means all. */
  fallback?: string[];
};
export type RangeFilter = { kind: "range"; key: string; label: string };
export type FilterDef = ListFilter | RangeFilter;

/** In USD. A missing side is open. */
export type Range = { min?: number; max?: number };

const MILLION = 1_000_000;

export function readList(params: URLSearchParams, key: string, fallback: string[] = []) {
  if (!params.has(key)) return fallback;
  return (params.get(key) ?? "").split(",").filter(Boolean);
}

export function optionValue(option: FilterOption) {
  return typeof option === "string" ? option : option.value;
}

export function optionLabel(option: FilterOption) {
  return typeof option === "string" ? option : option.label;
}

export function readRange(params: URLSearchParams, key: string): Range {
  const [min, max] = (params.get(key) ?? "").split("-");
  const toUsd = (text: string | undefined) => (text ? Number(text) * MILLION : undefined);
  return { min: toUsd(min), max: toUsd(max) };
}

export function writeList(values: string[]) {
  return values.join(",");
}

export function writeRange({ min, max }: Range) {
  if (min === undefined && max === undefined) return "";
  return `${min === undefined ? "" : min / MILLION}-${max === undefined ? "" : max / MILLION}`;
}

/** True when nothing is picked, or one of the item's values is picked. */
export function anyOf(picked: string[], values: string[]) {
  return picked.length === 0 || values.some((value) => picked.includes(value));
}

/** An unknown value only passes an open range. */
export function inRange(value: number | null | undefined, range: Range) {
  if (value === undefined || value === null) return range.min === undefined && range.max === undefined;
  return (range.min === undefined || value >= range.min) && (range.max === undefined || value <= range.max);
}

/** True when the item's own range (a buyer's check size) overlaps the filter. A missing side is open. */
export function overlaps(min: number | null, max: number | null, range: Range) {
  return (range.max === undefined || min === null || min <= range.max) && (range.min === undefined || max === null || max >= range.min);
}

/** True when every word typed appears somewhere in the given texts (case does not matter). */
export function matchesText(query: string, texts: (string | undefined)[]) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const haystack = texts.join(" ").toLowerCase();
  return words.every((word) => haystack.includes(word));
}
