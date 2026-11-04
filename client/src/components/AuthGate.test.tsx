import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

import { AuthGate } from "./AuthGate";

function serve(routes: Record<string, () => Response>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const path = new URL(url, "http://localhost").pathname;
      const handler = routes[path];
      return Promise.resolve(
        handler ? handler() : jsonResponse(404, { detail: null }),
      );
    }),
  );
}

const unauthorized = (): Response =>
  jsonResponse(401, {
    detail: { code: "unauthorized", message: "Sign in to continue." },
  });

describe("AuthGate", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
    sessionStorage.clear();
  });

  it("shows the app to someone signed in with Slack", async () => {
    serve({
      "/api/auth/config": () =>
        jsonResponse(200, { slack_sign_in: true, api_key: false }),
      "/api/auth/me": () =>
        jsonResponse(200, { slack_user_id: "U1", name: "Alice", via: "slack" }),
    });
    renderWithQuery(<AuthGate>app content</AuthGate>);

    expect(await screen.findByText("app content")).toBeInTheDocument();
  });

  it("offers Sign in with Slack that returns to the same page", async () => {
    window.history.replaceState(null, "", "/app/runs/42");
    serve({
      "/api/auth/config": () =>
        jsonResponse(200, { slack_sign_in: true, api_key: false }),
      "/api/auth/me": unauthorized,
    });
    renderWithQuery(<AuthGate>app content</AuthGate>);

    const link = await screen.findByRole("link", {
      name: "Sign in with Slack",
    });
    expect(link).toHaveAttribute(
      "href",
      "/api/auth/slack/login?next=%2Fapp%2Fruns%2F42",
    );
    expect(screen.queryByText("app content")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Use an access key instead" }),
    ).toBeNull();
  });

  it("falls back to the access key where the server allows it", async () => {
    serve({
      "/api/auth/config": () =>
        jsonResponse(200, { slack_sign_in: true, api_key: true }),
      "/api/auth/me": unauthorized,
    });
    renderWithQuery(<AuthGate>app content</AuthGate>);

    await userEvent.click(
      await screen.findByRole("button", { name: "Use an access key instead" }),
    );

    expect(screen.getByLabelText("Access key")).toBeInTheDocument();
  });

  it("explains a refused sign-in", async () => {
    window.history.replaceState(null, "", "/app/?signin_error=wrong_workspace");
    serve({
      "/api/auth/config": () =>
        jsonResponse(200, { slack_sign_in: true, api_key: false }),
      "/api/auth/me": unauthorized,
    });
    renderWithQuery(<AuthGate>app content</AuthGate>);

    expect(
      await screen.findByText("Sign in with your Wusool Slack account."),
    ).toBeInTheDocument();
  });
});
