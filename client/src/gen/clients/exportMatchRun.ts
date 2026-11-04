// @ts-nocheck

import type { ExportMatchRunOptions, ExportMatchRunResponses } from '../types/ExportMatchRun'
import type { Options, RequestResult } from '@/lib/api-client'
import { exportMatchRunResponseSchema, exportMatchRunErrorSchema } from '../zod/exportMatchRunSchema'
import { client } from '@/lib/api-client'

/**
 * @description `fields` picks and orders the columns; omitted, every column is exported.
 * @summary Export Match Run
 * {@link /api/match-runs/:run_id/export.csv}
 */
export function exportMatchRun<ThrowOnError extends boolean = true>(options: Options<ExportMatchRunOptions, ThrowOnError>): Promise<RequestResult<ExportMatchRunResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/match-runs/{run_id}/export.csv', validator: { response: exportMatchRunResponseSchema, error: exportMatchRunErrorSchema }, responseType: 'text', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<ExportMatchRunResponses, ThrowOnError>>
}
