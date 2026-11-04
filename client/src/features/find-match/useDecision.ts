import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";

import { approveCandidate } from "@/gen/clients/approveCandidate";
import { rejectCandidate } from "@/gen/clients/rejectCandidate";
import { getMatchRunQueryKey } from "@/gen/hooks/useGetMatchRun";
import type { ApproveRequest } from "@/gen/types/ApproveRequest";
import type { DecisionResponse } from "@/gen/types/DecisionResponse";
import type { ExistingDealRead } from "@/gen/types/ExistingDealRead";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";
import { ApiRequestError } from "@/lib/api-client";

export type Decision =
  { kind: "approve"; resolution?: ApproveRequest } | { kind: "reject" };

interface Snapshot {
  previous: RunDetailResponse | undefined;
}

export function existingDeals(error: unknown): ExistingDealRead[] | null {
  if (
    !(error instanceof ApiRequestError) ||
    error.detail?.code !== "existing_deals"
  )
    return null;
  return error.detail.existing_deals ?? [];
}

export function useDecision(
  runId: string,
  candidateId: string,
): UseMutationResult<DecisionResponse, Error, Decision, Snapshot> {
  const queryClient = useQueryClient();
  const queryKey = getMatchRunQueryKey({ path: { run_id: runId } });

  return useMutation<DecisionResponse, Error, Decision, Snapshot>({
    mutationFn: async (decision) => {
      const path = { run_id: runId, candidate_id: candidateId };
      const result =
        decision.kind === "approve"
          ? await approveCandidate({ path, body: decision.resolution ?? {} })
          : await rejectCandidate({ path });
      return result.data;
    },
    onMutate: async (decision) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RunDetailResponse>(queryKey);
      const status = decision.kind === "approve" ? "APPROVED" : "REJECTED";
      queryClient.setQueryData<RunDetailResponse>(queryKey, (run) =>
        run === undefined
          ? run
          : {
              ...run,
              candidates: run.candidates.map((c) =>
                c.id === candidateId ? { ...c, status, decision: status } : c,
              ),
            },
      );
      return { previous };
    },
    onError: (_error, _decision, snapshot) => {
      if (snapshot?.previous !== undefined)
        queryClient.setQueryData(queryKey, snapshot.previous);
    },
    onSuccess: ({ candidate }) => {
      queryClient.setQueryData<RunDetailResponse>(queryKey, (run) =>
        run === undefined
          ? run
          : {
              ...run,
              candidates: run.candidates.map((c) =>
                c.id === candidate.id ? candidate : c,
              ),
            },
      );
    },
  });
}
