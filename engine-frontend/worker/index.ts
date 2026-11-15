// Serves the app and forwards /api/v1/* to the Toolkit from the server side, so the browser only
// talks to this hostname: no CORS and no cross-site cookie. Cloudflare Access has already signed
// the request (Cf-Access-Jwt-Assertion) before it reaches this Worker, and the Toolkit checks that
// token itself, so the origin refuses calls that did not come through Access.

type Env = {
  ASSETS: { fetch: (request: Request) => Promise<Response> };
  /** The Toolkit's public base URL, set in wrangler.jsonc. */
  TOOLKIT_ORIGIN: string;
};

const API_PREFIX = "/api/v1/";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      // Anything else under /api would fall through to index.html and answer 200 with a web page.
      if (!url.pathname.startsWith(API_PREFIX)) return Response.json({ code: "not_found" }, { status: 404 });
      const proxied = new Request(new URL(url.pathname + url.search, env.TOOLKIT_ORIGIN), request);
      // The Access session cookie carries the same token as the header; the Toolkit only needs the header.
      proxied.headers.delete("cookie");
      return fetch(proxied);
    }
    return env.ASSETS.fetch(request);
  },
};
