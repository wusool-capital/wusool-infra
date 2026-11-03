// @ts-nocheck

import type { StartMatchRunOptions, StartMatchRunResponses } from '../types/StartMatchRun'
import type { Options, RequestResult } from '@/lib/api-client'
import { startMatchRunResponseSchema, startMatchRunErrorSchema } from '../zod/startMatchRunSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Start Match Run
 * {@link /api/match-runs}
 */
export function startMatchRun<ThrowOnError extends boolean = true>(options: Options<StartMatchRunOptions, ThrowOnError>): Promise<RequestResult<StartMatchRunResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs', validator: { response: startMatchRunResponseSchema, error: startMatchRunErrorSchema }, contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<StartMatchRunResponses, ThrowOnError>>
}
