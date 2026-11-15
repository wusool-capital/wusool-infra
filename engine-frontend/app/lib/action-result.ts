import { isResponseError } from "../gen/.kubb/client";
import type { ProblemDetail } from "../gen/types/ProblemDetail";

/** What a route action hands back; a refusal carries a sentence the drawer can show. */
export type ActionResult = { error?: string };

function describe(problem: unknown) {
  const body = problem as Partial<ProblemDetail> | null;
  if (typeof body?.detail !== "string") return "The server could not be reached. Try again.";
  return body.errors?.length ? `${body.detail} ${body.errors.join("; ")}` : body.detail;
}

/** A sentence for a failure no screen handled itself, such as a loader that could not reach the Toolkit. */
export function errorMessage(error: unknown): string {
  if (isResponseError(error)) {
    if (error.status === 401) return "Your sign-in has expired. Reload the page to sign in again.";
    if (error.status === 403) return "Your email is not set up for the Engine. Ask an admin to add it in Attio.";
    return describe(error.data);
  }
  return error instanceof Error ? error.message : "Something unexpected went wrong.";
}

/** Turns a Toolkit refusal into a message. Anything else is a bug, so it still throws. */
export async function attempt(run: () => Promise<unknown>): Promise<ActionResult> {
  try {
    await run();
    return {};
  } catch (error) {
    if (isResponseError(error)) return { error: describe(error.data) };
    throw error;
  }
}

/** The fields of `draft` that differ from `initial`, so a save sends only what the person changed. */
export function changedFields<T extends object>(initial: T, draft: T): Partial<T> {
  const changed: Partial<T> = {};
  for (const key of Object.keys(draft) as (keyof T)[]) {
    if (JSON.stringify(draft[key]) !== JSON.stringify(initial[key])) changed[key] = draft[key];
  }
  return changed;
}
