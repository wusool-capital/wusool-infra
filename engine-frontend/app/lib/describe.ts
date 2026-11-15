// Turns a plain sentence into Buyers or Sellers search filters (decided 7 Nov 2026).
// Once live, the smallest model tier reads the sentence and returns these same fields; the demo
// uses word rules. Either way it only fills the filters: nothing runs until the person clicks Search.

const SECTOR_WORDS: [RegExp, string][] = [
  [/\bvet|veterinar|animal|pet\b/i, "Veterinary"],
  [/dental|dentist|ortho/i, "Dental"],
  [/logistic|freight|cold.?chain|haulage|cargo|trucking/i, "Logistics"],
  [/nurser|school|education/i, "Education"],
  [/coffee|roast|bakery|bakeries|food|beverage|cafe/i, "Food and beverage"],
  // "clinic" alone is not here: vet and dental clinics have their own sectors.
  [/health|hospital|medical|diagnostic|lab\b|labs\b/i, "Healthcare"],
  [/facility|cleaning|security|business services/i, "Business services"],
  [/retail|stores?\b/i, "Retail"],
];
const PLACE_WORDS: [RegExp, string][] = [
  [/\buae\b|dubai|abu dhabi|sharjah|emirates/i, "UAE"],
  [/\bksa\b|saudi|riyadh|jeddah|dammam/i, "KSA"],
  [/qatar|doha/i, "Qatar"],
  [/kuwait/i, "Kuwait"],
  [/oman|muscat/i, "Oman"],
  [/bahrain|manama/i, "Bahrain"],
  [/europe|\buk\b|london/i, "Europe"],
];
const TYPE_WORDS: [RegExp, string][] = [
  [/family offices?/i, "Family office"],
  [/private equity|\bpe\b|funds?\b|sponsors?/i, "Private equity"],
  [/strategic|corporates?|groups?\b/i, "Strategic"],
];
// Words that carry no search meaning once the filters are set.
const FILLER = new Set(
  "a an and or the of for in on at to into with who that which are is do does doing looking look find buyers buyer sellers seller owners owner companies company firms firm buying buy acquiring acquire selling sell open between from under over above below less more than up million usd m cheques cheque check size sizes revenue ebitda last years year gcc region clinic clinics business businesses group groups chain chains".split(" "),
);

type Options = { sectors: string[]; geographies: string[]; types?: string[]; amountKey: string; ebitdaKey?: string };

export function filtersFromDescription(text: string, options: Options) {
  const params = new URLSearchParams();
  const pick = (rules: [RegExp, string][], allowed: string[]) => [...new Set(rules.filter(([pattern]) => pattern.test(text)).map(([, value]) => value))].filter((value) => allowed.includes(value));

  const sectors = pick(SECTOR_WORDS, options.sectors);
  if (sectors.length) params.set("sector", sectors.join(","));
  const places = /\bgcc\b/i.test(text) ? [] : pick(PLACE_WORDS, options.geographies);
  if (places.length) params.set("geography", places.join(","));
  if (options.types) {
    // "Family office" also contains "office"; take the first matching type only.
    const [type] = pick(TYPE_WORDS, options.types);
    if (type) params.set("type", type);
  }

  // Amounts in $M: "$5M to $20M", "5-20m", "over $10M", "under 20m". EBITDA goes to its own filter.
  const key = options.ebitdaKey && /ebitda/i.test(text) ? options.ebitdaKey : options.amountKey;
  const between = text.match(/\$?(\d+(?:\.\d+)?)\s*m?\s*(?:to|-|and)\s*\$?(\d+(?:\.\d+)?)\s*m/i);
  const over = text.match(/(?:over|above|more than|from)\s*\$?(\d+(?:\.\d+)?)\s*m/i);
  const under = text.match(/(?:under|below|less than|up to)\s*\$?(\d+(?:\.\d+)?)\s*m/i);
  if (between) params.set(key, `${between[1]}-${between[2]}`);
  else if (over || under) params.set(key, `${over ? over[1] : ""}-${under ? under[1] : ""}`);

  // What is left (for example "roll-ups") becomes keywords, matched against names and rationales.
  // Every word (or phrase, like "private equity") that set a filter is removed first.
  let rest = text.replace(/\$?\d+(?:\.\d+)?\s*m\b/gi, " ");
  for (const [pattern] of [...SECTOR_WORDS, ...PLACE_WORDS, ...TYPE_WORDS]) {
    rest = rest.replace(new RegExp(`[^\\s,.;]*(?:${pattern.source})[^\\s,.;]*`, "gi"), " ");
  }
  const keywords = rest.split(/[\s,.;]+/).filter((word) => word && !FILLER.has(word.toLowerCase()) && !/\d/.test(word));
  if (keywords.length) params.set("q", keywords.join(" "));
  return params;
}
