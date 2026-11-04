// @ts-nocheck

import type { SkipResearchOptions, SkipResearchStatus200, SkipResearchStatus401, SkipResearchStatus404, SkipResearchStatus409, SkipResearchStatus422, SkipResearchStatus503 } from '../types/SkipResearch'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { skipResearch } from '../clients/skipResearch'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const skipResearchMutationKey = () => [{ url: '/api/match-runs/:run_id/candidates/:candidate_id/research/skip' }] as const

export function skipResearchMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = skipResearchMutationKey()
  return mutationOptions<SkipResearchStatus200, ResponseErrorConfig<SkipResearchStatus401 | SkipResearchStatus404 | SkipResearchStatus409 | SkipResearchStatus422 | SkipResearchStatus503>, SkipResearchOptions, TContext>({
    mutationKey,
    mutationFn: async({ path }) => {
      return (await skipResearch({ ...config, path, throwOnError: true })).data
    },
  })
}

/**
 * @summary Skip Research
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/research/skip}
 */
export function useSkipResearch<TContext>(options: {
  mutation?: UseMutationOptions<SkipResearchStatus200, ResponseErrorConfig<SkipResearchStatus401 | SkipResearchStatus404 | SkipResearchStatus409 | SkipResearchStatus422 | SkipResearchStatus503>, SkipResearchOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? skipResearchMutationKey()

  const baseOptions = skipResearchMutationOptions(config) as UseMutationOptions<SkipResearchStatus200, ResponseErrorConfig<SkipResearchStatus401 | SkipResearchStatus404 | SkipResearchStatus409 | SkipResearchStatus422 | SkipResearchStatus503>, SkipResearchOptions, TContext>

  return useMutation<SkipResearchStatus200, ResponseErrorConfig<SkipResearchStatus401 | SkipResearchStatus404 | SkipResearchStatus409 | SkipResearchStatus422 | SkipResearchStatus503>, SkipResearchOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<SkipResearchStatus200, ResponseErrorConfig<SkipResearchStatus401 | SkipResearchStatus404 | SkipResearchStatus409 | SkipResearchStatus422 | SkipResearchStatus503>, SkipResearchOptions, TContext>
}
