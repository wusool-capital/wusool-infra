import { QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import { candidate, jsonResponse, run, RUN_ID } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import {
  DiscoverySection,
  MandateSection,
  Review,
  RunProgress,
} from "./RunReview";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: React.ReactNode }) => (
    <a href="/app/find-match">{children}</a>
  ),
}));

describe("run review", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows progress while matching runs", () => {
    renderWithQuery(
      <RunProgress run={run({ state: "running", completed_at: null })} />,
    );
    expect(screen.getByText(/Reading the mandate/)).toBeInTheDocument();
  });

  it("explains a stale run and offers a new one", () => {
    renderWithQuery(
      <RunProgress run={run({ state: "stale", completed_at: null })} />,
    );
    expect(screen.getByText("This run never finished")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Start a new run" }),
    ).toBeInTheDocument();
  });

  it("shows a failed run's error", () => {
    renderWithQuery(
      <RunProgress
        run={run({ state: "failed", error: "matching failed early" })}
      />,
    );
    expect(screen.getByText(/matching failed early/)).toBeInTheDocument();
  });

  it("says when no CRM seller qualified", () => {
    renderWithQuery(<Review run={run({ candidates: [] })} />);
    expect(screen.getByText(/No seller in the CRM passed/)).toBeInTheDocument();
  });

  it("warns about low match quality", () => {
    renderWithQuery(
      <Review
        run={run({
          low_match_quality: true,
          candidates: [candidate({ match_score: 31 })],
        })}
      />,
    );
    expect(
      screen.getByText(/best score is 31, below the 50 threshold/),
    ).toBeInTheDocument();
  });

  it("offers a manual search when discovery is available", () => {
    renderWithQuery(
      <DiscoverySection
        run={run({
          discovery: { status: "available", message: null, notes: [] },
        })}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Find more sellers" }),
    ).toBeInTheDocument();
  });

  it("lets the advisor search anyway when the shortlist is good", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(
          202,
          run({ discovery: { status: "running", message: null, notes: [] } }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<DiscoverySection run={run()} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Find more sellers anyway" }),
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce();
    });
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/match-runs/${RUN_ID}/discovery`,
    );
  });

  it("says when fewer than three CRM sellers qualified, as Slack does", () => {
    renderWithQuery(<Review run={run()} />);
    expect(
      screen.getByText("Only 1 qualifying candidate available — fewer than 3."),
    ).toBeInTheDocument();
  });

  it("shows the buyer's mandate from the run", () => {
    renderWithQuery(
      <MandateSection
        run={run({
          mandate: {
            strategic_thesis: "Roll up GCC clinics",
            ideal_target: null,
            hard_requirements: [
              {
                criterion: "sector",
                value: "Healthcare Services / Clinics",
                source: "crm_field",
                human_confirmed: true,
              },
            ],
          },
        })}
      />,
    );
    expect(screen.getByText("Roll up GCC clinics")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(
      screen.getByText(/sector: Healthcare Services \/ Clinics/),
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
      <Review
        run={run({
          low_match_quality: true,
          discovery: {
            status: "done",
            message: "Found 1 new seller(s).",
            notes: ["2 more already in the CRM."],
          },
          candidates: [candidate({ status: "REJECTED" }), found],
        })}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Found outside the CRM · 1" }),
    ).toBeInTheDocument();
    expect(screen.getByText("2 more already in the CRM.")).toBeInTheDocument();
  });

  it("opens the first pending candidate and moves on after a decision", async () => {
    const first = candidate();
    const second = candidate({
      id: "5e4d3c2b-1a0f-4e9d-8c7b-6a5f4e3d2c1b",
      rank: 2,
      seller_org_name: "Riyadh Physio Group",
    });
    const current = run({ candidates: [first, second] });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          candidate: { ...first, status: "REJECTED", decision: "REJECTED" },
          research_channel_id: null,
        }),
      ),
    );
    const { client, rerender } = renderWithQuery(<Review run={current} />);
    const key = getMatchRunQueryKey({ path: { run_id: RUN_ID } });
    client.setQueryData(key, current);

    expect(
      screen.getByRole("heading", { level: 3, name: "Gulf Dental Partners" }),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    rerender(
      <QueryClientProvider client={client}>
        <Review run={client.getQueryData(key) ?? current} />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 3, name: "Riyadh Physio Group" }),
      ).toBeInTheDocument();
    });
  });
});
