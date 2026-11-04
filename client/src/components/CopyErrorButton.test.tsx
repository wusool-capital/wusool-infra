import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CopyErrorButton } from "./CopyErrorButton";

describe("CopyErrorButton", () => {
  it("copies the error with the page it happened on", async () => {
    const user = userEvent.setup();
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined);
    window.history.replaceState(null, "", "/app/runs/42");
    render(<CopyErrorButton message="Attio API error 400" />);

    await user.click(screen.getByRole("button", { name: "Copy error" }));

    const copied = writeText.mock.calls[0]?.[0] ?? "";
    expect(copied).toContain("Attio API error 400");
    expect(copied).toContain("Page: http://localhost:3000/app/runs/42");
    expect(copied).toMatch(/Time: \d{4}-\d{2}-\d{2}T/);
    expect(
      await screen.findByRole("button", { name: "Copied" }),
    ).toBeInTheDocument();
  });
});
