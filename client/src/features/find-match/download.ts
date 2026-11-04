import { authHeaders, buildUrl } from "@/lib/api-client";
import type { ExportField } from "@/lib/export-fields";

// A plain link can't carry the API key header, so fetch the file and hand it to the browser.
export async function downloadRunCsv(
  runId: string,
  fields: readonly ExportField[],
): Promise<void> {
  const response = await fetch(
    buildUrl({
      url: "/api/match-runs/{run_id}/export.csv",
      path: { run_id: runId },
      query: { fields: [...fields] },
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
  // Some browsers start the download after click() returns; revoking now would cancel it.
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}
