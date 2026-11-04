// @ts-nocheck

import type { PreflightOptions, PreflightResponses } from '../types/Preflight'
import type { Options, RequestResult } from '@/lib/api-client'
import { preflightResponseSchema2, preflightErrorSchema } from '../zod/preflightSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Preflight
 * {@link /api/buyers/:buyer_role_id/preflight}
 */
export function preflight<ThrowOnError extends boolean = true>(options: Options<PreflightOptions, ThrowOnError>): Promise<RequestResult<PreflightResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/buyers/{buyer_role_id}/preflight', validator: { response: preflightResponseSchema2, error: preflightErrorSchema }, contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<PreflightResponses, ThrowOnError>>
}
