// @ts-nocheck

import type { GetAuthConfigStatus200 } from '../types/GetAuthConfig'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { QueryKey, QueryClient, QueryObserverOptions, UseQueryResult } from '@tanstack/react-query'
import { getAuthConfig } from '../clients/getAuthConfig'
import { queryOptions, useQuery } from '@tanstack/react-query'

export const getAuthConfigQueryKey = () => [{ url: '/api/auth/config' }] as const

type GetAuthConfigQueryKey = ReturnType<typeof getAuthConfigQueryKey>

export function getAuthConfigQueryOptions(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const queryKey = getAuthConfigQueryKey()
  return queryOptions<GetAuthConfigStatus200, ResponseErrorConfig<Error>, GetAuthConfigStatus200, typeof queryKey>({
   queryKey,
   queryFn: async ({ signal }) => {
      return (await getAuthConfig({ ...config, signal: config.signal ?? signal, throwOnError: true })).data
   },
  })
}

/**
 * @summary Get Auth Config
 * {@link /api/auth/config}
 */
export function useGetAuthConfig<TData = GetAuthConfigStatus200, TQueryData = GetAuthConfigStatus200, TQueryKey extends QueryKey = GetAuthConfigQueryKey>(options: {
  query?: Partial<QueryObserverOptions<GetAuthConfigStatus200, ResponseErrorConfig<Error>, TData, TQueryData, TQueryKey>> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>
} = {}) {
  const { query: queryConfig = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...resolvedOptions } = queryConfig
  const queryKey = resolvedOptions?.queryKey ?? getAuthConfigQueryKey()

  const queryResult = useQuery({
   ...getAuthConfigQueryOptions(config),
   ...resolvedOptions,
   queryKey,
  } as unknown as QueryObserverOptions, queryClient) as UseQueryResult<TData, ResponseErrorConfig<Error>> & { queryKey: TQueryKey }

  queryResult.queryKey = queryKey as TQueryKey

  return queryResult
}
