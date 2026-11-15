// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { AddBuyerOptions, AddBuyerResponses } from '../types/AddBuyer'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `POST /api/v1/buyer-roles`
 * @summary Add Buyer
 */
export function addBuyer<ThrowOnError extends boolean = true>(options: Options<AddBuyerOptions, ThrowOnError>): Unwrappable<RequestResult<AddBuyerResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<AddBuyerResponses, ThrowOnError>({ method: 'POST', url: '/api/v1/buyer-roles', contentType: { request: 'application/json' }, ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
