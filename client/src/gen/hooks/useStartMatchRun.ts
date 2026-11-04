// @ts-nocheck

import type { StartMatchRunOptions, StartMatchRunStatus202, StartMatchRunStatus401, StartMatchRunStatus404, StartMatchRunStatus422, StartMatchRunStatus503 } from '../types/StartMatchRun'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { startMatchRun } from '../clients/startMatchRun'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const startMatchRunMutationKey = () => [{ url: '/api/match-runs' }] as const

export function startMatchRunMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = startMatchRunMutationKey()
  return mutationOptions<StartMatchRunStatus202, ResponseErrorConfig<StartMatchRunStatus401 | StartMatchRunStatus404 | StartMatchRunStatus422 | StartMatchRunStatus503>, StartMatchRunOptions, TContext>({
    mutationKey,
    mutationFn: async({ body }) => {
      return (await startMatchRun({ ...config, body, throwOnError: true })).data
    },
  })
}

/**
 * @summary Start Match Run
 * {@link /api/match-runs}
 */
export function useStartMatchRun<TContext>(options: {
  mutation?: UseMutationOptions<StartMatchRunStatus202, ResponseErrorConfig<StartMatchRunStatus401 | StartMatchRunStatus404 | StartMatchRunStatus422 | StartMatchRunStatus503>, StartMatchRunOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? startMatchRunMutationKey()

  const baseOptions = startMatchRunMutationOptions(config) as UseMutationOptions<StartMatchRunStatus202, ResponseErrorConfig<StartMatchRunStatus401 | StartMatchRunStatus404 | StartMatchRunStatus422 | StartMatchRunStatus503>, StartMatchRunOptions, TContext>

  return useMutation<StartMatchRunStatus202, ResponseErrorConfig<StartMatchRunStatus401 | StartMatchRunStatus404 | StartMatchRunStatus422 | StartMatchRunStatus503>, StartMatchRunOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<StartMatchRunStatus202, ResponseErrorConfig<StartMatchRunStatus401 | StartMatchRunStatus404 | StartMatchRunStatus422 | StartMatchRunStatus503>, StartMatchRunOptions, TContext>
}
