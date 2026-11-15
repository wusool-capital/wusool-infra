// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { GetBuyerRoleOptions, GetBuyerRoleResponses } from '../types/GetBuyerRole'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/buyer-roles/{role_id}`
 * @summary Get Buyer Role
 */
export function getBuyerRole<ThrowOnError extends boolean = true>(options: Options<GetBuyerRoleOptions, ThrowOnError>): Unwrappable<RequestResult<GetBuyerRoleResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<GetBuyerRoleResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/buyer-roles/{role_id}', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
