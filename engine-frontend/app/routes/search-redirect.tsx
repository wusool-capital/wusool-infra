import { redirect } from "react-router";
import type { Route } from "./+types/search-redirect";

// Buyers and Sellers search became one Search page (8 Nov 2026); old links still land on it.
export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const url = new URL(request.url);
  return redirect(`${url.pathname.startsWith("/sellers") ? "/search/sellers" : "/search/buyers"}${url.search}`);
}

export default function SearchRedirect() {
  return null;
}
