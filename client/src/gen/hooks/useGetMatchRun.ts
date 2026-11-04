// @ts-nocheck

import type { GetMatchRunOptions, GetMatchRunStatus200, GetMatchRunStatus401, GetMatchRunStatus404, GetMatchRunStatus422, GetMatchRunStatus503 } from '../types/GetMatchRun'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { QueryKey, QueryClient, QueryObserverOptions, UseQueryResult } from '@tanstack/react-query'
import { getMatchRun } from '../clients/getMatchRun'
import { queryOptions, useQuery } from '@tanstack/react-query'

export const getMatchRunQueryKey = ({ path }: Omit<GetMatchRunOptions, 'headers'>) => [{ url: '/api/match-runs/:run_id', params: path }] as const

type GetMatchRunQueryKey = ReturnType<typeof getMatchRunQueryKey>

export function getMatchRunQueryOptions({ path }: GetMatchRunOptions, config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const queryKey = getMatchRunQueryKey({ path })
  return queryOptions<GetMatchRunStatus200, ResponseErrorConfig<GetMatchRunStatus401 | GetMatchRunStatus404 | GetMatchRunStatus422 | GetMatchRunStatus503>, GetMatchRunStatus200, typeof queryKey>({
   queryKey,
   queryFn: async ({ signal }) => {
      return (await getMatchRun({ ...config, path, signal: config.signal ?? signal, throwOnError: true })).data
   },
  })
}

/**
 * @summary Get Match Run
 * {@link /api/match-runs/:run_id}
 */
export function useGetMatchRun<TData = GetMatchRunStatus200, TQueryData = GetMatchRunStatus200, TQueryKey extends QueryKey = GetMatchRunQueryKey>({ path }: { path: GetMatchRunOptions['path'] | (() => GetMatchRunOptions['path']) }, options: {
  query?: Partial<QueryObserverOptions<GetMatchRunStatus200, ResponseErrorConfig<GetMatchRunStatus401 | GetMatchRunStatus404 | GetMatchRunStatus422 | GetMatchRunStatus503>, TData, TQueryData, TQueryKey>> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>
} = {}) {
  const { query: queryConfig = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...resolvedOptions } = queryConfig
  const resolvedParams = { path: typeof path === 'function' ? path() : path }
  const queryKey = resolvedOptions?.queryKey ?? getMatchRunQueryKey(resolvedParams)

  const queryResult = useQuery({
   ...getMatchRunQueryOptions(resolvedParams, config),
   ...resolvedOptions,
   queryKey,
  } as unknown as QueryObserverOptions, queryClient) as UseQueryResult<TData, ResponseErrorConfig<GetMatchRunStatus401 | GetMatchRunStatus404 | GetMatchRunStatus422 | GetMatchRunStatus503>> & { queryKey: TQueryKey }

  queryResult.queryKey = queryKey as TQueryKey

  return queryResult
}
