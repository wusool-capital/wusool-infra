import { redirect } from "react-router";
import type { Route } from "./+types/mandates-redirect";

export async function clientLoader({ params, request }: Route.ClientLoaderArgs) {
  return redirect(params.dealId ? `/deals/${params.dealId}${new URL(request.url).search}` : "/pipeline?view=list");
}

export default function MandatesRedirect() {
  return null;
}
