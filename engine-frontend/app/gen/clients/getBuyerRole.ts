// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { GetBuyerRoleOptions, GetBuyerRoleResponses } from '../types/GetBuyerRole'
import { client } from '../../lib/api-client'

/**
 * @summary Get Buyer Role
 * {@link /api/v1/buyer-roles/:role_id}
 */
export function getBuyerRole<ThrowOnError extends boolean = true>(options: Options<GetBuyerRoleOptions, ThrowOnError>): Promise<RequestResult<GetBuyerRoleResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/buyer-roles/{role_id}', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetBuyerRoleResponses, ThrowOnError>>
}
