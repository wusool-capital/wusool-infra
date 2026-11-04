// @ts-nocheck

import type { SaveResearchOptions, SaveResearchStatus200, SaveResearchStatus401, SaveResearchStatus403, SaveResearchStatus404, SaveResearchStatus409, SaveResearchStatus422, SaveResearchStatus502, SaveResearchStatus503 } from '../types/SaveResearch'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { saveResearch } from '../clients/saveResearch'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const saveResearchMutationKey = () => [{ url: '/api/match-runs/:run_id/candidates/:candidate_id/research/save' }] as const

export function saveResearchMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = saveResearchMutationKey()
  return mutationOptions<SaveResearchStatus200, ResponseErrorConfig<SaveResearchStatus401 | SaveResearchStatus403 | SaveResearchStatus404 | SaveResearchStatus409 | SaveResearchStatus422 | SaveResearchStatus502 | SaveResearchStatus503>, SaveResearchOptions, TContext>({
    mutationKey,
    mutationFn: async({ path, body }) => {
      return (await saveResearch({ ...config, path, body, throwOnError: true })).data
    },
  })
}

/**
 * @summary Save Research
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/research/save}
 */
export function useSaveResearch<TContext>(options: {
  mutation?: UseMutationOptions<SaveResearchStatus200, ResponseErrorConfig<SaveResearchStatus401 | SaveResearchStatus403 | SaveResearchStatus404 | SaveResearchStatus409 | SaveResearchStatus422 | SaveResearchStatus502 | SaveResearchStatus503>, SaveResearchOptions, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? saveResearchMutationKey()

  const baseOptions = saveResearchMutationOptions(config) as UseMutationOptions<SaveResearchStatus200, ResponseErrorConfig<SaveResearchStatus401 | SaveResearchStatus403 | SaveResearchStatus404 | SaveResearchStatus409 | SaveResearchStatus422 | SaveResearchStatus502 | SaveResearchStatus503>, SaveResearchOptions, TContext>

  return useMutation<SaveResearchStatus200, ResponseErrorConfig<SaveResearchStatus401 | SaveResearchStatus403 | SaveResearchStatus404 | SaveResearchStatus409 | SaveResearchStatus422 | SaveResearchStatus502 | SaveResearchStatus503>, SaveResearchOptions, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<SaveResearchStatus200, ResponseErrorConfig<SaveResearchStatus401 | SaveResearchStatus403 | SaveResearchStatus404 | SaveResearchStatus409 | SaveResearchStatus422 | SaveResearchStatus502 | SaveResearchStatus503>, SaveResearchOptions, TContext>
}
