// Every page keeps its filters, view, search and open item in the URL. Remembering the last URL
// lets a link bring you back to a page as you left it, not to its defaults. Kept in memory only:
// a browser reload starts fresh.
const byPath = new Map<string, string>();
const bySection = new Map<string, string>();

/** "/search/sellers" belongs to "/search"; Search's Buyers and Sellers sides share one nav item. */
const sectionOf = (pathname: string) => `/${pathname.split("/")[1] ?? ""}`;

export function rememberUrl(pathname: string, search: string) {
  const url = `${pathname}${search}`;
  byPath.set(pathname, url);
  bySection.set(sectionOf(pathname), url);
}

/** The last URL seen at exactly this path, for switches between sibling pages. */
export const lastUrlAt = (pathname: string) => byPath.get(pathname) ?? pathname;

/** The last URL seen anywhere in this path's section, for nav links. */
export const lastUrlInSection = (pathname: string) => bySection.get(sectionOf(pathname)) ?? pathname;
