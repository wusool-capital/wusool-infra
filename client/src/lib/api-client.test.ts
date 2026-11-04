import { z } from "zod";

import { jsonResponse } from "@/test/fixtures";

import { ApiRequestError, buildUrl, client } from "./api-client";
import { getApiKey, setApiKey } from "./api-key";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setApiKey(null);
  });

  it("sends the key and validates the response", async () => {
    setApiKey("secret");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { run_id: "x" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await client({
      method: "GET",
      url: "/api/match-runs/{run_id}",
      path: { run_id: "a b" },
      validator: { response: z.object({ run_id: z.string() }) },
    });

    const [url, init] = fetchMock.mock.lastCall as [string, RequestInit];
    expect(url).toBe("/api/match-runs/a%20b");
    expect(init.headers).toMatchObject({ Authorization: "Bearer secret" });
    expect(result.data).toEqual({ run_id: "x" });
  });

  it("rejects a response in the wrong shape instead of rendering it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { run_id: 1 })),
    );

    await expect(
      client({
        method: "GET",
        url: "/x",
        validator: { response: z.object({ run_id: z.string() }) },
      }),
    ).rejects.toThrow("unexpected shape");
  });

  it("forgets a rejected key", async () => {
    setApiKey("stale");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(401, {
          detail: { code: "unauthorized", message: "Invalid API key." },
        }),
      ),
    );

    const error: unknown = await client({ method: "GET", url: "/x" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).detail?.code).toBe("unauthorized");
    expect(getApiKey()).toBeNull();
  });

  it("repeats a list query parameter", () => {
    expect(
      buildUrl({ url: "/x", query: { fields: ["seller", "match_score"] } }),
    ).toMatch(/\/x\?fields=seller&fields=match_score$/);
  });
});
