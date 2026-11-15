// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { UpdateBuyerOptions, UpdateBuyerResponses } from '../types/UpdateBuyer'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `PATCH /api/v1/buyer-roles/{role_id}`
 * @summary Update Buyer
 */
export function updateBuyer<ThrowOnError extends boolean = true>(options: Options<UpdateBuyerOptions, ThrowOnError>): Unwrappable<RequestResult<UpdateBuyerResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<UpdateBuyerResponses, ThrowOnError>({ method: 'PATCH', url: '/api/v1/buyer-roles/{role_id}', contentType: { request: 'application/json' }, ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
