const ACRONYMS: Record<string, string> = {
  hq: "HQ",
  url: "URL",
  arr: "ARR",
  pct: "%",
  ebitda: "EBITDA",
};

// Field names as people read them: sector_focus -> "Sector focus".
export function fieldLabel(name: string): string {
  const words = name
    .split("_")
    .map((word) => ACRONYMS[word] ?? word)
    .join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
