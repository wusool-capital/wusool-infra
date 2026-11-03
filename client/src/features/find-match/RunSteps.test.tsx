import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { candidate, run } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import { DiscoveryStep, MatchingStep, ShortlistStep } from "./RunSteps";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: React.ReactNode }) => (
    <a href="/app/find-match">{children}</a>
  ),
}));

describe("run steps", () => {
  it("shows progress while matching runs", () => {
    renderWithQuery(
      <MatchingStep
        run={run({ state: "running", completed_at: null })}
        state="active"
      />,
    );
    expect(screen.getByText(/Reading the mandate/)).toBeInTheDocument();
  });

  it("explains a stale run and offers a new one", () => {
    renderWithQuery(
      <MatchingStep
        run={run({ state: "stale", completed_at: null })}
        state="attention"
      />,
    );
    expect(screen.getByText("This run never finished")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Start a new run" }),
    ).toBeInTheDocument();
  });

  it("shows a failed run's error", () => {
    renderWithQuery(
      <MatchingStep
        run={run({ state: "failed", error: "matching failed early" })}
        state="attention"
      />,
    );
    expect(screen.getByText(/matching failed early/)).toBeInTheDocument();
  });

  it("says when no CRM seller qualified", async () => {
    renderWithQuery(
      <ShortlistStep run={run({ candidates: [] })} state="done" />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /No CRM seller qualified/ }),
    );
    expect(screen.getByText(/No seller in the CRM passed/)).toBeInTheDocument();
  });

  it("warns about low match quality", () => {
    renderWithQuery(
      <ShortlistStep
        run={run({
          low_match_quality: true,
          candidates: [candidate({ match_score: 31 })],
        })}
        state="active"
      />,
    );
    expect(
      screen.getByText(/best score is 31, below the 50 threshold/),
    ).toBeInTheDocument();
  });

  it("offers a manual search when discovery is available", () => {
    renderWithQuery(
      <DiscoveryStep
        run={run({
          discovery: { status: "available", message: null, notes: [] },
        })}
        state="active"
      />,
    );
    expect(
      screen.getByRole("button", { name: "Find more sellers" }),
    ).toBeInTheDocument();
  });

  it("lists discovered sellers for review", () => {
    const found = candidate({
      id: "0d1c2b3a-4f5e-6d7c-8b9a-0f1e2d3c4b5a",
      origin: "discovery",
      seller_org_name: "Al Noor Dental",
      match_score: null,
      source_url: "https://alnoor.example",
    });
    renderWithQuery(
      <DiscoveryStep
        run={run({
          low_match_quality: true,
          discovery: {
            status: "done",
            message: "Found 1 new seller(s).",
            notes: ["2 more already in the CRM."],
          },
          candidates: [candidate({ status: "REJECTED" }), found],
        })}
        state="active"
      />,
    );
    expect(screen.getByText("Al Noor Dental")).toBeInTheDocument();
    expect(screen.getByText("2 more already in the CRM.")).toBeInTheDocument();
  });
});
