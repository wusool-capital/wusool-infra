import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import { BuyerSearch } from "./BuyerSearch";

const buyers = [
  {
    id: "b1",
    organization: {
      name: "Najd Healthcare Holdings",
      hq_country: "Saudi Arabia",
      sector_focus: [],
    },
    model: "Strategic",
    mandate_status: "Active",
    target_vertical: "Healthcare",
  },
  {
    id: "b2",
    organization: { name: "Najd Capital", hq_country: null, sector_focus: [] },
    model: null,
    mandate_status: null,
    target_vertical: null,
  },
];

describe("BuyerSearch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks for two letters before searching", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<BuyerSearch initialQuery="" onPick={vi.fn()} />);

    expect(screen.getByText("Type at least 2 letters.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("picks the highlighted buyer with the arrow keys and Enter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, buyers)),
    );
    const onPick = vi.fn();
    renderWithQuery(<BuyerSearch initialQuery="" onPick={onPick} />);

    await userEvent.type(screen.getByRole("combobox"), "najd");
    expect(
      await screen.findByRole("option", { name: /Najd Capital/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Healthcare · Saudi Arabia · Strategic · Active"),
    ).toBeInTheDocument();
    expect(screen.getByText("No mandate details yet")).toBeInTheDocument();

    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ id: "b2" }));
  });

  it("says when nothing matches", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));
    renderWithQuery(<BuyerSearch initialQuery="zzz" onPick={vi.fn()} />);

    expect(
      await screen.findByText(/No buyer matches “zzz”/),
    ).toBeInTheDocument();
  });

  it("offers a retry when the search fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(500, { detail: "boom" }))
      .mockResolvedValue(jsonResponse(200, buyers));
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<BuyerSearch initialQuery="najd" onPick={vi.fn()} />);

    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(screen.getAllByRole("option")).toHaveLength(2);
    });
  });
});
