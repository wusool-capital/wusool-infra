import type { ShouldRevalidateFunctionArgs } from "react-router";

/** Reload a list only on a filter change or a save; opening a drawer must not call the Toolkit. */
export function reloadOnFilterChange(keys: readonly string[]) {
  return ({ currentUrl, nextUrl, formMethod, defaultShouldRevalidate }: ShouldRevalidateFunctionArgs) => {
    if (formMethod) return defaultShouldRevalidate;
    return keys.some((key) => currentUrl.searchParams.get(key) !== nextUrl.searchParams.get(key));
  };
}
