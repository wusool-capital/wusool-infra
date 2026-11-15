// Every date and time renders in Dubai time so all viewers see the same day boundaries.
const TIME_ZONE = "Asia/Dubai";

const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: TIME_ZONE });
const shortDateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: TIME_ZONE });
const weekdayFormat = new Intl.DateTimeFormat("en-GB", { weekday: "long", timeZone: TIME_ZONE });
const timeFormat = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TIME_ZONE });
const dayKeyFormat = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE });

// Date-only values ("2026-11-12") are read as midday Dubai so no time zone shifts the day.
function toDate(value: string) {
  return new Date(value.length === 10 ? `${value}T12:00:00+04:00` : value);
}

/** "12 Mar 2026" */
export function formatDate(value: string) {
  return dateFormat.format(toDate(value));
}

/** "Wednesday 11 Nov 2026" */
export function formatLongDate(value: string) {
  return `${weekdayFormat.format(toDate(value))} ${formatDate(value)}`;
}

/** "09:30" */
export function formatTime(value: string) {
  return timeFormat.format(toDate(value));
}

/** "2026-11-11" in Dubai time, for comparing days. */
export function dayKey(value: string) {
  return dayKeyFormat.format(toDate(value));
}

function addDays(value: string, days: number) {
  return dayKey(new Date(toDate(value).getTime() + days * 86_400_000).toISOString());
}

/** "08:12" today, "Yesterday 17:40", otherwise "6 Nov 16:20". */
export function formatWhen(value: string, now: string) {
  const day = dayKey(value);
  if (day === dayKey(now)) return formatTime(value);
  if (day === addDays(now, -1)) return `Yesterday ${formatTime(value)}`;
  return `${shortDateFormat.format(toDate(value))} ${formatTime(value)}`;
}

/** "$14.5M" or "$850K" for deal sizes. */
export function formatMoney(usd: number | null | undefined) {
  if (usd === undefined || usd === null) return "Not set";
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  return `$${Math.round(usd / 1_000)}K`;
}

/** "$10M to $40M" */
export function formatMoneyRange(min: number | null, max: number | null) {
  if (min === null && max === null) return "Not set";
  return `${formatMoney(min)} to ${formatMoney(max)}`;
}

/** "1 company", "3 companies". */
export function count(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

/** "$435,000" for fees and exact amounts. */
export function formatUsd(usd: number) {
  return `$${Math.round(usd).toLocaleString("en-US")}`;
}

/** Hours between two timestamps. */
export function hoursBetween(from: string, to: string) {
  return (toDate(to).getTime() - toDate(from).getTime()) / 3_600_000;
}
