// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { GetSellerRoleOptions, GetSellerRoleResponses } from '../types/GetSellerRole'
import { client } from '../../lib/api-client'

/**
 * @summary Get Seller Role
 * {@link /api/v1/seller-roles/:role_id}
 */
export function getSellerRole<ThrowOnError extends boolean = true>(options: Options<GetSellerRoleOptions, ThrowOnError>): Promise<RequestResult<GetSellerRoleResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/seller-roles/{role_id}', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetSellerRoleResponses, ThrowOnError>>
}
