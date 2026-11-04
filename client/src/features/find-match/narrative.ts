export type NarrativeBlock =
  { kind: "text"; text: string } | { kind: "list"; items: string[] };

const BULLET = /^\s*[-•]\s+/;

// Runs written before the bulleted prompt number their points inline ("1. … 2. …").
function splitInlineNumbering(text: string): string {
  if (text.includes("\n") || !/^\s*1\.\s/.test(text)) return text;
  return text.replace(/\s+(?=\d{1,2}\.\s)/g, "\n");
}

// Groups consecutive bullet lines into one list; every other line is its own paragraph.
export function parseNarrative(text: string): NarrativeBlock[] {
  const blocks: NarrativeBlock[] = [];
  for (const raw of splitInlineNumbering(text).split("\n")) {
    const line = raw.trim();
    if (line === "") continue;
    const last = blocks.at(-1);
    if (BULLET.test(line)) {
      const item = line.replace(BULLET, "");
      if (last?.kind === "list") last.items.push(item);
      else blocks.push({ kind: "list", items: [item] });
    } else {
      blocks.push({ kind: "text", text: line });
    }
  }
  return blocks;
}
