// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { ListBuyerRolesOptions, ListBuyerRolesResponses } from '../types/ListBuyerRoles'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/buyer-roles`
 * @summary List Buyer Roles
 */
export function listBuyerRoles<ThrowOnError extends boolean = true>(options: Options<ListBuyerRolesOptions, ThrowOnError> = {}): Unwrappable<RequestResult<ListBuyerRolesResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<ListBuyerRolesResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/buyer-roles', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
