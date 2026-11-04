import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";

import { saveResearch } from "@/gen/clients/saveResearch";
import { skipResearch } from "@/gen/clients/skipResearch";
import { startResearch } from "@/gen/clients/startResearch";
import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { DecisionResponse } from "@/gen/types/DecisionResponse";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { ApiRequestError } from "@/lib/api-client";

export type ResearchAction =
  { kind: "save"; fields: string[] } | { kind: "skip" } | { kind: "retry" };

// Fields someone filled in since the research ran, from a 409 on save.
export function conflictingFields(error: unknown): string[] {
  return error instanceof ApiRequestError &&
    error.detail?.code === "research_conflict"
    ? (error.detail.fields ?? [])
    : [];
}

export function useResearch(
  runId: string,
  candidateId: string,
): UseMutationResult<DecisionResponse, Error, ResearchAction> {
  const queryClient = useQueryClient();
  const queryKey = getMatchRunQueryKey({ path: { run_id: runId } });

  return useMutation<DecisionResponse, Error, ResearchAction>({
    mutationFn: async (action) => {
      const path = { run_id: runId, candidate_id: candidateId };
      const result =
        action.kind === "save"
          ? await saveResearch({ path, body: { fields: action.fields } })
          : action.kind === "skip"
            ? await skipResearch({ path })
            : await startResearch({ path });
      return result.data;
    },
    onSuccess: ({ candidate }) => {
      queryClient.setQueryData<RunDetailResponse>(queryKey, (run) =>
        run === undefined
          ? run
          : {
              ...run,
              candidates: run.candidates.map((c: CandidateRead) =>
                c.id === candidate.id ? candidate : c,
              ),
            },
      );
    },
  });
}
