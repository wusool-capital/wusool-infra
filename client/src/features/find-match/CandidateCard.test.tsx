import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { candidate, jsonResponse, run, RUN_ID } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import { CandidateCard } from "./CandidateCard";

const existingDeals = {
  detail: {
    code: "existing_deals",
    message: "Attio already has a deal for this buyer and seller.",
    existing_deals: [
      {
        attio_id: "deal-1",
        name: "Gulf Dental - Najd",
        stage: "Inbound",
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
    <CandidateCard runId={RUN_ID} candidate={candidate()} threshold={50} />,
  );
  const key = getMatchRunQueryKey({ path: { run_id: RUN_ID } });
  client.setQueryData(key, run());
  return {
    cachedStatus: () =>
      client.getQueryData<RunDetailResponse>(key)?.candidates[0]?.status,
  };
}

describe("CandidateCard", () => {
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
      jsonResponse(200, { candidate: candidate({ status: "APPROVED" }) }),
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
});
