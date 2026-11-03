// @ts-nocheck

import type { ExportMatchRunOptions, ExportMatchRunStatus200, ExportMatchRunStatus401, ExportMatchRunStatus404, ExportMatchRunStatus422, ExportMatchRunStatus503 } from '../types/ExportMatchRun'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { QueryKey, QueryClient, QueryObserverOptions, UseQueryResult } from '@tanstack/react-query'
import { exportMatchRun } from '../clients/exportMatchRun'
import { queryOptions, useQuery } from '@tanstack/react-query'

export const exportMatchRunQueryKey = ({ path }: Omit<ExportMatchRunOptions, 'headers'>) => [{ url: '/api/match-runs/:run_id/export.csv', params: path }] as const

type ExportMatchRunQueryKey = ReturnType<typeof exportMatchRunQueryKey>

export function exportMatchRunQueryOptions({ path }: ExportMatchRunOptions, config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const queryKey = exportMatchRunQueryKey({ path })
  return queryOptions<ExportMatchRunStatus200, ResponseErrorConfig<ExportMatchRunStatus401 | ExportMatchRunStatus404 | ExportMatchRunStatus422 | ExportMatchRunStatus503>, ExportMatchRunStatus200, typeof queryKey>({
   queryKey,
   queryFn: async ({ signal }) => {
      return (await exportMatchRun({ ...config, path, signal: config.signal ?? signal, throwOnError: true })).data
   },
  })
}

/**
 * @summary Export Match Run
 * {@link /api/match-runs/:run_id/export.csv}
 */
export function useExportMatchRun<TData = ExportMatchRunStatus200, TQueryData = ExportMatchRunStatus200, TQueryKey extends QueryKey = ExportMatchRunQueryKey>({ path }: { path: ExportMatchRunOptions['path'] | (() => ExportMatchRunOptions['path']) }, options: {
  query?: Partial<QueryObserverOptions<ExportMatchRunStatus200, ResponseErrorConfig<ExportMatchRunStatus401 | ExportMatchRunStatus404 | ExportMatchRunStatus422 | ExportMatchRunStatus503>, TData, TQueryData, TQueryKey>> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>
} = {}) {
  const { query: queryConfig = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...resolvedOptions } = queryConfig
  const resolvedParams = { path: typeof path === 'function' ? path() : path }
  const queryKey = resolvedOptions?.queryKey ?? exportMatchRunQueryKey(resolvedParams)

  const queryResult = useQuery({
   ...exportMatchRunQueryOptions(resolvedParams, config),
   ...resolvedOptions,
   queryKey,
  } as unknown as QueryObserverOptions, queryClient) as UseQueryResult<TData, ResponseErrorConfig<ExportMatchRunStatus401 | ExportMatchRunStatus404 | ExportMatchRunStatus422 | ExportMatchRunStatus503>> & { queryKey: TQueryKey }

  queryResult.queryKey = queryKey as TQueryKey

  return queryResult
}
