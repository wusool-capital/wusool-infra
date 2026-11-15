// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { ListSellerRolesOptions, ListSellerRolesResponses } from '../types/ListSellerRoles'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/seller-roles`
 * @summary List Seller Roles
 */
export function listSellerRoles<ThrowOnError extends boolean = true>(options: Options<ListSellerRolesOptions, ThrowOnError> = {}): Unwrappable<RequestResult<ListSellerRolesResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<ListSellerRolesResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/seller-roles', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
