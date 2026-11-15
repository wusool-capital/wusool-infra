import type { ShouldRevalidateFunctionArgs } from "react-router";

/**
 * Reload a list only when one of its filters changes or after a save. Opening a drawer
 * changes the URL too, but must not call the Toolkit again.
 */
export function reloadOnFilterChange(keys: readonly string[]) {
  return ({ currentUrl, nextUrl, formMethod, defaultShouldRevalidate }: ShouldRevalidateFunctionArgs) => {
    if (formMethod) return defaultShouldRevalidate;
    return keys.some((key) => currentUrl.searchParams.get(key) !== nextUrl.searchParams.get(key));
  };
}
