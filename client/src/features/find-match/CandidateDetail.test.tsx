import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { candidate, jsonResponse, run, RUN_ID } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import { CandidateDetail } from "./CandidateDetail";

const existingDeals = {
  detail: {
    code: "existing_deals",
    message: "Attio already has a deal for this buyer and seller.",
    existing_deals: [
      {
        attio_id: "deal-1",
        name: "Gulf Dental - Najd",
        stage: "Lead",
        web_url: null,
      },
    ],
  },
};

function setup(fetchMock: ReturnType<typeof vi.fn>): {
  cachedStatus: () => string | undefined;
} {
  vi.stubGlobal("fetch", fetchMock);
  const { client } = renderWithQuery(
    <CandidateDetail runId={RUN_ID} candidate={candidate()} threshold={50} />,
  );
  const key = getMatchRunQueryKey({ path: { run_id: RUN_ID } });
  client.setQueryData(key, run());
  return {
    cachedStatus: () =>
      client.getQueryData<RunDetailResponse>(key)?.candidates[0]?.status,
  };
}

describe("CandidateDetail", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the score against the discovery threshold", () => {
    setup(vi.fn());
    expect(screen.getByRole("meter", { name: "Match score" })).toHaveAttribute(
      "aria-valuetext",
      "78 of 100",
    );
  });

  it("rejects optimistically", async () => {
    const decided = candidate({ status: "REJECTED", decision: "REJECTED" });
    const { cachedStatus } = setup(
      vi.fn().mockResolvedValue(jsonResponse(200, { candidate: decided })),
    );

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() => {
      expect(cachedStatus()).toBe("REJECTED");
    });
  });

  it("rolls back and offers the existing deals on a 409", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(409, existingDeals));
    const { cachedStatus } = setup(fetchMock);

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(
      await screen.findByText(
        "Attio already has a deal for this buyer and seller",
      ),
    ).toBeInTheDocument();
    expect(cachedStatus()).toBe("PENDING_REVIEW");

    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        candidate: candidate({ status: "APPROVED" }),
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Use this deal" }),
    );

    const [, init] = fetchMock.mock.lastCall as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      resolution: "promote_existing",
      existing_deal_id: "deal-1",
    });
  });

  it("shows the server's message when approval fails", async () => {
    setup(
      vi.fn().mockResolvedValue(
        jsonResponse(502, {
          detail: {
            code: "partial_write",
            message: "Couldn't write the deal to Attio.",
          },
        }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Couldn't write the deal to Attio.",
    );
  });

  it("shows Slack's criteria breakdown for a CRM seller", () => {
    setup(vi.fn());
    const criteria = screen.getByRole("region", { name: "Criteria" });
    expect(criteria).toHaveTextContent("sector");
    expect(criteria).toHaveTextContent("Pass");
  });

  it("shows what discovery found about a discovered seller", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWithQuery(
      <CandidateDetail
        runId={RUN_ID}
        threshold={50}
        candidate={candidate({
          origin: "discovery",
          match_score: null,
          criteria: [],
          source_url: "https://maps.google.com/?cid=1",
          profile: {
            description: "Cold storage near Jebel Ali.",
            hq_country: "United Arab Emirates",
            sector_focus: ["Logistics / 3PL / Freight"],
            website: "reefer.example",
            employee_range: "11-50",
            founded_year: 2012,
            location_count: null,
            est_revenue: null,
            est_ebitda: null,
          },
        })}
      />,
    );

    expect(
      screen.getByText(/Unverified and unscored; approve to open a Qualified/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View on Maps/ })).toHaveAttribute(
      "href",
      "https://maps.google.com/?cid=1",
    );
    const profile = screen.getByRole("region", { name: "Company profile" });
    expect(profile).toHaveTextContent("Cold storage near Jebel Ali.");
    expect(profile).toHaveTextContent("2012");
    expect(
      screen.getByRole("link", { name: "reefer.example" }),
    ).toHaveAttribute("href", "https://reefer.example");
    expect(screen.queryByRole("region", { name: "Criteria" })).toBeNull();
  });

  it("offers at most three existing deals, linked to Attio", async () => {
    const deals = [1, 2, 3, 4].map((n) => ({
      attio_id: `deal-${String(n)}`,
      name: `Deal ${String(n)}`,
      stage: "Lead",
      web_url: `https://app.attio.com/deal-${String(n)}`,
    }));
    setup(
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          detail: { ...existingDeals.detail, existing_deals: deals },
        }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(
      await screen.findAllByRole("button", { name: "Use this deal" }),
    ).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Deal 1/ })).toHaveAttribute(
      "href",
      "https://app.attio.com/deal-1",
    );
  });
});
