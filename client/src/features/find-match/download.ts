import { authHeaders, buildUrl } from "@/lib/api-client";

// A plain link can't carry the API key header, so fetch the file and hand it to the browser.
export async function downloadRunCsv(runId: string): Promise<void> {
  const response = await fetch(
    buildUrl({
      url: "/api/match-runs/{run_id}/export.csv",
      path: { run_id: runId },
    }),
    { headers: authHeaders() },
  );
  if (!response.ok)
    throw new Error(`Export failed (${String(response.status)})`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `find-match-${runId}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
