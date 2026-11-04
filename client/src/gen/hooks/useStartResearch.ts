// @ts-nocheck

import type { StartResearchOptions, StartResearchStatus202, StartResearchStatus401, StartResearchStatus404, StartResearchStatus409, StartResearchStatus422, StartResearchStatus503 } from '../types/StartResearch'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { startResearch } from '../clients/startResearch'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const startResearchMutationKey = () => [{ url: '/api/match-runs/:run_id/candidates/:candidate_id/research' }] as const

export function startResearchMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = startResearchMutationKey()
  return mutationOptions<StartResearchStatus202, ResponseErrorConfig<StartResearchStatus401 | StartResearchStatus404 | StartResearchStatus409 | StartResearchStatus422 | StartResearchStatus503>, StartResearchOptions, TContext>({
    mutationKey,
    mutationFn: async({ path }) => {
      return (await startResearch({ ...config, path, throwOnError: true })).data
    },
  })
}

/**
 * @description Starts or retries the research; the claim makes a repeat a no-op.
 * @summary Start Research
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/research}
 */
export function useStartResearch<TContext>(options: {
  mutation?: UseMutationOptions<StartResearchStatus202, ResponseErrorConfig<StartResearchStatus401 | StartResearchStatus404 | StartResearchStatus409 | StartResearchStatus422 | StartResearchStatus503>, StartResearchOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? startResearchMutationKey()

  const baseOptions = startResearchMutationOptions(config) as UseMutationOptions<StartResearchStatus202, ResponseErrorConfig<StartResearchStatus401 | StartResearchStatus404 | StartResearchStatus409 | StartResearchStatus422 | StartResearchStatus503>, StartResearchOptions, TContext>

  return useMutation<StartResearchStatus202, ResponseErrorConfig<StartResearchStatus401 | StartResearchStatus404 | StartResearchStatus409 | StartResearchStatus422 | StartResearchStatus503>, StartResearchOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<StartResearchStatus202, ResponseErrorConfig<StartResearchStatus401 | StartResearchStatus404 | StartResearchStatus409 | StartResearchStatus422 | StartResearchStatus503>, StartResearchOptions, TContext>
}
