// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { GetSellerRoleOptions, GetSellerRoleResponses } from '../types/GetSellerRole'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/seller-roles/{role_id}`
 * @summary Get Seller Role
 */
export function getSellerRole<ThrowOnError extends boolean = true>(options: Options<GetSellerRoleOptions, ThrowOnError>): Unwrappable<RequestResult<GetSellerRoleResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<GetSellerRoleResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/seller-roles/{role_id}', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
