// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { AddSellerOptions, AddSellerResponses } from '../types/AddSeller'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `POST /api/v1/seller-roles`
 * @summary Add Seller
 */
export function addSeller<ThrowOnError extends boolean = true>(options: Options<AddSellerOptions, ThrowOnError>): Unwrappable<RequestResult<AddSellerResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<AddSellerResponses, ThrowOnError>({ method: 'POST', url: '/api/v1/seller-roles', contentType: { request: 'application/json' }, ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
