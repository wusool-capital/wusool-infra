// @ts-nocheck

import type { ExportMatchRunOptions, ExportMatchRunStatus200, ExportMatchRunStatus401, ExportMatchRunStatus404, ExportMatchRunStatus422, ExportMatchRunStatus503 } from '../types/ExportMatchRun'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { QueryKey, QueryClient, QueryObserverOptions, UseQueryResult } from '@tanstack/react-query'
import { exportMatchRun } from '../clients/exportMatchRun'
import { queryOptions, useQuery } from '@tanstack/react-query'

export const exportMatchRunQueryKey = ({ path, query }: Omit<ExportMatchRunOptions, 'headers'>) => [{ url: '/api/match-runs/:run_id/export.csv', params: path }, ...(query ? [query] : [])] as const

type ExportMatchRunQueryKey = ReturnType<typeof exportMatchRunQueryKey>

export function exportMatchRunQueryOptions({ path, query }: ExportMatchRunOptions, config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const queryKey = exportMatchRunQueryKey({ path, query })
  return queryOptions<ExportMatchRunStatus200, ResponseErrorConfig<ExportMatchRunStatus401 | ExportMatchRunStatus404 | ExportMatchRunStatus422 | ExportMatchRunStatus503>, ExportMatchRunStatus200, typeof queryKey>({
   queryKey,
   queryFn: async ({ signal }) => {
      return (await exportMatchRun({ ...config, path, query, signal: config.signal ?? signal, throwOnError: true })).data
   },
  })
}

/**
 * @description `fields` picks and orders the columns; omitted, every column is exported.
 * @summary Export Match Run
 * {@link /api/match-runs/:run_id/export.csv}
 */
export function useExportMatchRun<TData = ExportMatchRunStatus200, TQueryData = ExportMatchRunStatus200, TQueryKey extends QueryKey = ExportMatchRunQueryKey>({ path, query }: { path: ExportMatchRunOptions['path'] | (() => ExportMatchRunOptions['path']); query?: ExportMatchRunOptions['query'] | (() => ExportMatchRunOptions['query']) }, options: {
  query?: Partial<QueryObserverOptions<ExportMatchRunStatus200, ResponseErrorConfig<ExportMatchRunStatus401 | ExportMatchRunStatus404 | ExportMatchRunStatus422 | ExportMatchRunStatus503>, TData, TQueryData, TQueryKey>> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>
} = {}) {
  const { query: queryConfig = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...resolvedOptions } = queryConfig
  const resolvedParams = { path: typeof path === 'function' ? path() : path, query: typeof query === 'function' ? query() : query }
  const queryKey = resolvedOptions?.queryKey ?? exportMatchRunQueryKey(resolvedParams)

  const queryResult = useQuery({
   ...exportMatchRunQueryOptions(resolvedParams, config),
   ...resolvedOptions,
   queryKey,
  } as unknown as QueryObserverOptions, queryClient) as UseQueryResult<TData, ResponseErrorConfig<ExportMatchRunStatus401 | ExportMatchRunStatus404 | ExportMatchRunStatus422 | ExportMatchRunStatus503>> & { queryKey: TQueryKey }

  queryResult.queryKey = queryKey as TQueryKey

  return queryResult
}
