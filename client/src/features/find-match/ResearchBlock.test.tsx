import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ResearchRead } from "@/gen/types/ResearchRead";
import { candidate, jsonResponse, RUN_ID } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import { ResearchBlock } from "./ResearchBlock";
import { fieldLabel } from "./research-labels";

const SELLER = "Sun-Securities & Services GmbH";

function research(overrides: Partial<ResearchRead> = {}): ResearchRead {
  return {
    status: "done",
    started_at: "2026-11-04T06:27:39Z",
    error: null,
    fields: [
      {
        name: "sector_focus",
        target: "organization",
        display: "Security Services",
        confidence: 0.9,
        source_url: "https://sun-securities.example",
        rationale: "Their site describes professional security services.",
        saved: false,
      },
      {
        name: "facebook",
        target: "organization",
        display: "https://facebook.com/sunsecurities",
        confidence: 0.6,
        source_url: "https://facebook.com/sunsecurities",
        rationale: "Page matches the Frankfurt address.",
        saved: false,
      },
    ],
    linkedin: {
      outcome: "completed",
      posts: [],
      job_changes: [],
      contacts_without_linkedin: 0,
    },
    reviewed: false,
    ...overrides,
  };
}

function show(value: ResearchRead | null): void {
  renderWithQuery(
    <ResearchBlock
      runId={RUN_ID}
      candidateId="c1"
      orgName={SELLER}
      research={value}
    />,
  );
}

describe("full research", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("says what it is doing while research runs", () => {
    show(research({ status: "running", fields: [], linkedin: null }));

    expect(screen.getByText(/Researching Sun-Securities/)).toBeInTheDocument();
  });

  it("ticks confident fields and saves the ticked ones", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        candidate: candidate({
          id: "c1",
          origin: "discovery",
          status: "APPROVED",
          research: research(),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    show(research());

    expect(screen.getByLabelText("Sector focus")).toBeChecked();
    expect(screen.getByLabelText("Facebook")).not.toBeChecked();
    await userEvent.click(
      screen.getByRole("button", { name: "Save 1 field to Attio" }),
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/candidates/c1/research/save");
    expect(JSON.parse(init.body as string)).toEqual({
      fields: ["sector_focus"],
    });
  });

  it("unticks fields filled in since and says so", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          detail: {
            code: "research_conflict",
            message: "Someone filled in these fields.",
            fields: ["sector_focus"],
          },
        }),
      ),
    );
    show(research());

    await userEvent.click(
      screen.getByRole("button", { name: "Save 1 field to Attio" }),
    );

    expect(
      await screen.findByText(/Someone filled in Sector focus/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Sector focus")).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "Save 0 fields to Attio" }),
    ).toBeDisabled();
  });

  it("offers a retry when research failed", () => {
    show(research({ status: "failed", error: "Research didn't finish." }));

    expect(screen.getByText("Research didn't finish.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });

  it("offers to run research that never started", () => {
    show(null);

    expect(
      screen.getByRole("button", { name: "Run full research" }),
    ).toBeInTheDocument();
  });

  it("shows saved fields as saved, with nothing left to tick", () => {
    show(
      research({
        fields: research().fields.map((f) => ({ ...f, saved: true })),
        reviewed: true,
      }),
    );

    expect(screen.getByText("Saved 2 fields to Attio.")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("locks the list and drops the buttons once skipped", () => {
    show(research({ reviewed: true }));

    expect(
      screen.getByText("Skipped. Nothing was saved to Attio."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Skip" })).toBeNull();
    for (const box of screen.getAllByRole("checkbox")) {
      expect(box).toBeDisabled();
      expect(box).not.toBeChecked();
    }
  });

  it("names fields the way people read them", () => {
    expect(fieldLabel("hq_country")).toBe("HQ country");
    expect(fieldLabel("gross_margin_pct")).toBe("Gross margin %");
  });
});
