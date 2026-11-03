// @ts-nocheck

import type { RejectCandidateOptions, RejectCandidateStatus200, RejectCandidateStatus401, RejectCandidateStatus404, RejectCandidateStatus409, RejectCandidateStatus422, RejectCandidateStatus503 } from '../types/RejectCandidate'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { rejectCandidate } from '../clients/rejectCandidate'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const rejectCandidateMutationKey = () => [{ url: '/api/match-runs/:run_id/candidates/:candidate_id/reject' }] as const

export function rejectCandidateMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = rejectCandidateMutationKey()
  return mutationOptions<RejectCandidateStatus200, ResponseErrorConfig<RejectCandidateStatus401 | RejectCandidateStatus404 | RejectCandidateStatus409 | RejectCandidateStatus422 | RejectCandidateStatus503>, RejectCandidateOptions, TContext>({
    mutationKey,
    mutationFn: async({ path }) => {
      return (await rejectCandidate({ ...config, path, throwOnError: true })).data
    },
  })
}

/**
 * @summary Reject Candidate
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/reject}
 */
export function useRejectCandidate<TContext>(options: {
  mutation?: UseMutationOptions<RejectCandidateStatus200, ResponseErrorConfig<RejectCandidateStatus401 | RejectCandidateStatus404 | RejectCandidateStatus409 | RejectCandidateStatus422 | RejectCandidateStatus503>, RejectCandidateOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? rejectCandidateMutationKey()

  const baseOptions = rejectCandidateMutationOptions(config) as UseMutationOptions<RejectCandidateStatus200, ResponseErrorConfig<RejectCandidateStatus401 | RejectCandidateStatus404 | RejectCandidateStatus409 | RejectCandidateStatus422 | RejectCandidateStatus503>, RejectCandidateOptions, TContext>

  return useMutation<RejectCandidateStatus200, ResponseErrorConfig<RejectCandidateStatus401 | RejectCandidateStatus404 | RejectCandidateStatus409 | RejectCandidateStatus422 | RejectCandidateStatus503>, RejectCandidateOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<RejectCandidateStatus200, ResponseErrorConfig<RejectCandidateStatus401 | RejectCandidateStatus404 | RejectCandidateStatus409 | RejectCandidateStatus422 | RejectCandidateStatus503>, RejectCandidateOptions, TContext>
}
