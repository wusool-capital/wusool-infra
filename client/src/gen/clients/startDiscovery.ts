// @ts-nocheck

import type { StartDiscoveryOptions, StartDiscoveryResponses } from '../types/StartDiscovery'
import type { Options, RequestResult } from '@/lib/api-client'
import { startDiscoveryResponseSchema, startDiscoveryErrorSchema } from '../zod/startDiscoverySchema'
import { client } from '@/lib/api-client'

/**
 * @description The web's "Find more sellers": a repeat call is a no-op, as in Slack.
 * @summary Start Discovery
 * {@link /api/match-runs/:run_id/discovery}
 */
export function startDiscovery<ThrowOnError extends boolean = true>(options: Options<StartDiscoveryOptions, ThrowOnError>): Promise<RequestResult<StartDiscoveryResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs/{run_id}/discovery', validator: { response: startDiscoveryResponseSchema, error: startDiscoveryErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<StartDiscoveryResponses, ThrowOnError>>
}
