// @ts-nocheck

import type { PreflightOptions, PreflightStatus200, PreflightStatus401, PreflightStatus404, PreflightStatus422, PreflightStatus503 } from '../types/Preflight'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { preflight } from '../clients/preflight'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const preflightMutationKey = () => [{ url: '/api/buyers/:buyer_role_id/preflight' }] as const

export function preflightMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = preflightMutationKey()
  return mutationOptions<PreflightStatus200, ResponseErrorConfig<PreflightStatus401 | PreflightStatus404 | PreflightStatus422 | PreflightStatus503>, PreflightOptions, TContext>({
    mutationKey,
    mutationFn: async({ path, body }) => {
      return (await preflight({ ...config, path, body, throwOnError: true })).data
    },
  })
}

/**
 * @summary Preflight
 * {@link /api/buyers/:buyer_role_id/preflight}
 */
export function usePreflight<TContext>(options: {
  mutation?: UseMutationOptions<PreflightStatus200, ResponseErrorConfig<PreflightStatus401 | PreflightStatus404 | PreflightStatus422 | PreflightStatus503>, PreflightOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? preflightMutationKey()

  const baseOptions = preflightMutationOptions(config) as UseMutationOptions<PreflightStatus200, ResponseErrorConfig<PreflightStatus401 | PreflightStatus404 | PreflightStatus422 | PreflightStatus503>, PreflightOptions, TContext>

  return useMutation<PreflightStatus200, ResponseErrorConfig<PreflightStatus401 | PreflightStatus404 | PreflightStatus422 | PreflightStatus503>, PreflightOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<PreflightStatus200, ResponseErrorConfig<PreflightStatus401 | PreflightStatus404 | PreflightStatus422 | PreflightStatus503>, PreflightOptions, TContext>
}
