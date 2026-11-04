// @ts-nocheck

import type { StartDiscoveryOptions, StartDiscoveryStatus202, StartDiscoveryStatus401, StartDiscoveryStatus404, StartDiscoveryStatus422, StartDiscoveryStatus503 } from '../types/StartDiscovery'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { startDiscovery } from '../clients/startDiscovery'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const startDiscoveryMutationKey = () => [{ url: '/api/match-runs/:run_id/discovery' }] as const

export function startDiscoveryMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = startDiscoveryMutationKey()
  return mutationOptions<StartDiscoveryStatus202, ResponseErrorConfig<StartDiscoveryStatus401 | StartDiscoveryStatus404 | StartDiscoveryStatus422 | StartDiscoveryStatus503>, StartDiscoveryOptions, TContext>({
    mutationKey,
    mutationFn: async({ path }) => {
      return (await startDiscovery({ ...config, path, throwOnError: true })).data
    },
  })
}

/**
 * @description The web's "Find more sellers": a repeat call is a no-op, as in Slack.
 * @summary Start Discovery
 * {@link /api/match-runs/:run_id/discovery}
 */
export function useStartDiscovery<TContext>(options: {
  mutation?: UseMutationOptions<StartDiscoveryStatus202, ResponseErrorConfig<StartDiscoveryStatus401 | StartDiscoveryStatus404 | StartDiscoveryStatus422 | StartDiscoveryStatus503>, StartDiscoveryOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? startDiscoveryMutationKey()

  const baseOptions = startDiscoveryMutationOptions(config) as UseMutationOptions<StartDiscoveryStatus202, ResponseErrorConfig<StartDiscoveryStatus401 | StartDiscoveryStatus404 | StartDiscoveryStatus422 | StartDiscoveryStatus503>, StartDiscoveryOptions, TContext>

  return useMutation<StartDiscoveryStatus202, ResponseErrorConfig<StartDiscoveryStatus401 | StartDiscoveryStatus404 | StartDiscoveryStatus422 | StartDiscoveryStatus503>, StartDiscoveryOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<StartDiscoveryStatus202, ResponseErrorConfig<StartDiscoveryStatus401 | StartDiscoveryStatus404 | StartDiscoveryStatus422 | StartDiscoveryStatus503>, StartDiscoveryOptions, TContext>
}
