import { parseNarrative } from "./narrative";

describe("parseNarrative", () => {
  it("groups dash bullets into one list", () => {
    expect(parseNarrative("- Ticket: unknown\n- Geography: blank")).toEqual([
      { kind: "list", items: ["Ticket: unknown", "Geography: blank"] },
    ]);
  });

  it("keeps a plain sentence as one paragraph", () => {
    expect(parseNarrative("Lead with the cybersecurity angle.")).toEqual([
      { kind: "text", text: "Lead with the cybersecurity angle." },
    ]);
  });

  it("splits older inline numbering onto its own lines", () => {
    expect(
      parseNarrative(
        "1. Sector: unclear. 2. Revenue: $15M is small. 3. Notes: none.",
      ),
    ).toEqual([
      { kind: "text", text: "1. Sector: unclear." },
      { kind: "text", text: "2. Revenue: $15M is small." },
      { kind: "text", text: "3. Notes: none." },
    ]);
  });

  it("leaves numbers mid-sentence alone", () => {
    expect(parseNarrative("Revenue of 15. 2 risks remain.")).toEqual([
      { kind: "text", text: "Revenue of 15. 2 risks remain." },
    ]);
  });
});
