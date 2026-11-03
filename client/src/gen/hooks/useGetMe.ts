// @ts-nocheck

import type { GetMeStatus200, GetMeStatus401, GetMeStatus422 } from '../types/GetMe'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { QueryKey, QueryClient, QueryObserverOptions, UseQueryResult } from '@tanstack/react-query'
import { getMe } from '../clients/getMe'
import { queryOptions, useQuery } from '@tanstack/react-query'

export const getMeQueryKey = () => [{ url: '/api/auth/me' }] as const

type GetMeQueryKey = ReturnType<typeof getMeQueryKey>

export function getMeQueryOptions(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const queryKey = getMeQueryKey()
  return queryOptions<GetMeStatus200, ResponseErrorConfig<GetMeStatus401 | GetMeStatus422>, GetMeStatus200, typeof queryKey>({
   queryKey,
   queryFn: async ({ signal }) => {
      return (await getMe({ ...config, signal: config.signal ?? signal, throwOnError: true })).data
   },
  })
}

/**
 * @summary Get Me
 * {@link /api/auth/me}
 */
export function useGetMe<TData = GetMeStatus200, TQueryData = GetMeStatus200, TQueryKey extends QueryKey = GetMeQueryKey>(options: {
  query?: Partial<QueryObserverOptions<GetMeStatus200, ResponseErrorConfig<GetMeStatus401 | GetMeStatus422>, TData, TQueryData, TQueryKey>> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>
} = {}) {
  const { query: queryConfig = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...resolvedOptions } = queryConfig
  const queryKey = resolvedOptions?.queryKey ?? getMeQueryKey()

  const queryResult = useQuery({
   ...getMeQueryOptions(config),
   ...resolvedOptions,
   queryKey,
  } as unknown as QueryObserverOptions, queryClient) as UseQueryResult<TData, ResponseErrorConfig<GetMeStatus401 | GetMeStatus422>> & { queryKey: TQueryKey }

  queryResult.queryKey = queryKey as TQueryKey

  return queryResult
}
