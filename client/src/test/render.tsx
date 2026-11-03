import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";

export function renderWithQuery(
  ui: React.ReactElement,
  client: QueryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  }),
): RenderResult & { client: QueryClient } {
  return {
    ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>),
    client,
  };
}
