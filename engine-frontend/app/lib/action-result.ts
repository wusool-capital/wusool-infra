import { isResponseError } from "../gen/.kubb/client";
import type { ProblemDetail } from "../gen/types/ProblemDetail";

/** What a route action hands back; a refusal carries a sentence the drawer can show. */
export type ActionResult = { error?: string };

function describe(problem: unknown) {
  const body = problem as Partial<ProblemDetail> | null;
  if (typeof body?.detail !== "string") return "The server could not be reached. Try again.";
  return body.errors?.length ? `${body.detail} ${body.errors.join("; ")}` : body.detail;
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
