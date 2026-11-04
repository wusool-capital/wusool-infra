// @ts-nocheck

import type { SearchBuyersOptions, SearchBuyersStatus200, SearchBuyersStatus401, SearchBuyersStatus404, SearchBuyersStatus422, SearchBuyersStatus503 } from '../types/SearchBuyers'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { QueryKey, QueryClient, QueryObserverOptions, UseQueryResult } from '@tanstack/react-query'
import { searchBuyers } from '../clients/searchBuyers'
import { queryOptions, useQuery } from '@tanstack/react-query'

export const searchBuyersQueryKey = ({ query }: Omit<SearchBuyersOptions, 'headers'>) => [{ url: '/api/buyers' }, ...(query ? [query] : [])] as const

type SearchBuyersQueryKey = ReturnType<typeof searchBuyersQueryKey>

export function searchBuyersQueryOptions({ query }: SearchBuyersOptions, config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const queryKey = searchBuyersQueryKey({ query })
  return queryOptions<SearchBuyersStatus200, ResponseErrorConfig<SearchBuyersStatus401 | SearchBuyersStatus404 | SearchBuyersStatus422 | SearchBuyersStatus503>, SearchBuyersStatus200, typeof queryKey>({
   queryKey,
   queryFn: async ({ signal }) => {
      return (await searchBuyers({ ...config, query, signal: config.signal ?? signal, throwOnError: true })).data
   },
  })
}

/**
 * @summary Search Buyers
 * {@link /api/buyers}
 */
export function useSearchBuyers<TData = SearchBuyersStatus200, TQueryData = SearchBuyersStatus200, TQueryKey extends QueryKey = SearchBuyersQueryKey>({ query }: { query: SearchBuyersOptions['query'] | (() => SearchBuyersOptions['query']) }, options: {
  query?: Partial<QueryObserverOptions<SearchBuyersStatus200, ResponseErrorConfig<SearchBuyersStatus401 | SearchBuyersStatus404 | SearchBuyersStatus422 | SearchBuyersStatus503>, TData, TQueryData, TQueryKey>> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>
} = {}) {
  const { query: queryConfig = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...resolvedOptions } = queryConfig
  const resolvedParams = { query: typeof query === 'function' ? query() : query }
  const queryKey = resolvedOptions?.queryKey ?? searchBuyersQueryKey(resolvedParams)

  const queryResult = useQuery({
   ...searchBuyersQueryOptions(resolvedParams, config),
   ...resolvedOptions,
   queryKey,
  } as unknown as QueryObserverOptions, queryClient) as UseQueryResult<TData, ResponseErrorConfig<SearchBuyersStatus401 | SearchBuyersStatus404 | SearchBuyersStatus422 | SearchBuyersStatus503>> & { queryKey: TQueryKey }

  queryResult.queryKey = queryKey as TQueryKey

  return queryResult
}
