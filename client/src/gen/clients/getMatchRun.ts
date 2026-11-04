// @ts-nocheck

import type { GetMatchRunOptions, GetMatchRunResponses } from '../types/GetMatchRun'
import type { Options, RequestResult } from '@/lib/api-client'
import { getMatchRunResponseSchema, getMatchRunErrorSchema } from '../zod/getMatchRunSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Get Match Run
 * {@link /api/match-runs/:run_id}
 */
export function getMatchRun<ThrowOnError extends boolean = true>(options: Options<GetMatchRunOptions, ThrowOnError>): Promise<RequestResult<GetMatchRunResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/match-runs/{run_id}', validator: { response: getMatchRunResponseSchema, error: getMatchRunErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetMatchRunResponses, ThrowOnError>>
}
