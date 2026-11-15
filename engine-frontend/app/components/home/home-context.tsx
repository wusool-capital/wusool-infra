import { useRouteAction } from "../ui/toast";

/** Posts an intent to the Home route action (the index route needs "?index"). */
export function useHomeAction() {
  return useRouteAction("/?index");
}
