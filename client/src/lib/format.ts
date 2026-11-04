const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

export function relativeTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  for (const [unit, size] of STEPS) {
    if (Math.abs(seconds) >= size)
      return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

const usd = new Intl.NumberFormat("en", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function money(value: number): string {
  return usd.format(value);
}

// match_score and data_confidence are both 0-100.
export function score(value: number | null | undefined): string {
  return value === null || value === undefined
    ? "—"
    : Math.round(value).toString();
}
