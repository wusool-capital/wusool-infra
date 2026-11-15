// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { UpdateSellerOptions, UpdateSellerResponses } from '../types/UpdateSeller'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `PATCH /api/v1/seller-roles/{role_id}`
 * @summary Update Seller
 */
export function updateSeller<ThrowOnError extends boolean = true>(options: Options<UpdateSellerOptions, ThrowOnError>): Unwrappable<RequestResult<UpdateSellerResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<UpdateSellerResponses, ThrowOnError>({ method: 'PATCH', url: '/api/v1/seller-roles/{role_id}', contentType: { request: 'application/json' }, ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
