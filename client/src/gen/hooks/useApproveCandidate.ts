// @ts-nocheck

import type { ApproveCandidateOptions, ApproveCandidateStatus200, ApproveCandidateStatus401, ApproveCandidateStatus404, ApproveCandidateStatus409, ApproveCandidateStatus422, ApproveCandidateStatus502, ApproveCandidateStatus503 } from '../types/ApproveCandidate'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { approveCandidate } from '../clients/approveCandidate'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const approveCandidateMutationKey = () => [{ url: '/api/match-runs/:run_id/candidates/:candidate_id/approve' }] as const

export function approveCandidateMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = approveCandidateMutationKey()
  return mutationOptions<ApproveCandidateStatus200, ResponseErrorConfig<ApproveCandidateStatus401 | ApproveCandidateStatus404 | ApproveCandidateStatus409 | ApproveCandidateStatus422 | ApproveCandidateStatus502 | ApproveCandidateStatus503>, ApproveCandidateOptions, TContext>({
    mutationKey,
    mutationFn: async({ path, body }) => {
      return (await approveCandidate({ ...config, path, body, throwOnError: true })).data
    },
  })
}

/**
 * @summary Approve Candidate
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/approve}
 */
export function useApproveCandidate<TContext>(options: {
  mutation?: UseMutationOptions<ApproveCandidateStatus200, ResponseErrorConfig<ApproveCandidateStatus401 | ApproveCandidateStatus404 | ApproveCandidateStatus409 | ApproveCandidateStatus422 | ApproveCandidateStatus502 | ApproveCandidateStatus503>, ApproveCandidateOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? approveCandidateMutationKey()

  const baseOptions = approveCandidateMutationOptions(config) as UseMutationOptions<ApproveCandidateStatus200, ResponseErrorConfig<ApproveCandidateStatus401 | ApproveCandidateStatus404 | ApproveCandidateStatus409 | ApproveCandidateStatus422 | ApproveCandidateStatus502 | ApproveCandidateStatus503>, ApproveCandidateOptions, TContext>

  return useMutation<ApproveCandidateStatus200, ResponseErrorConfig<ApproveCandidateStatus401 | ApproveCandidateStatus404 | ApproveCandidateStatus409 | ApproveCandidateStatus422 | ApproveCandidateStatus502 | ApproveCandidateStatus503>, ApproveCandidateOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<ApproveCandidateStatus200, ResponseErrorConfig<ApproveCandidateStatus401 | ApproveCandidateStatus404 | ApproveCandidateStatus409 | ApproveCandidateStatus422 | ApproveCandidateStatus502 | ApproveCandidateStatus503>, ApproveCandidateOptions, TContext>
}
