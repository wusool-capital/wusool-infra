import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/home.tsx"),
  route("pipeline", "routes/pipeline.tsx"),
  route("deals/:dealId", "routes/deal-view.tsx"),
  // Mandates merged into Pipeline (7 Nov 2026); old links still land on the right page.
  route("mandates", "routes/mandates-redirect.tsx", { id: "mandates-redirect" }),
  route("mandates/:dealId", "routes/mandates-redirect.tsx", { id: "mandate-redirect" }),
  route("outreach", "routes/outreach.tsx"),
  route("buyers/universe", "routes/buyers-universe.tsx"),
  route("search/buyers", "routes/buyers-search.tsx"),
  route("search/sellers", "routes/sellers-search.tsx"),
  route("buyers/search", "routes/search-redirect.tsx", { id: "buyers-search-redirect" }),
  route("sellers/search", "routes/search-redirect.tsx", { id: "sellers-search-redirect" }),
  route("sellers/universe", "routes/sellers-universe.tsx"),
  route("scorecards", "routes/scorecards.tsx"),
  route("partners", "routes/partners.tsx"),
  route("optimization", "routes/optimization.tsx"),
  route("multiples", "routes/multiples.tsx"),
  route("settings/skills", "routes/skills.tsx"),
  route("profile", "routes/profile.tsx"),
  route("signed-out", "routes/signed-out.tsx"),
  route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
