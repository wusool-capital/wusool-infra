// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { UpdateBuyerOptions, UpdateBuyerResponses } from '../types/UpdateBuyer'
import { client } from '../../lib/api-client'

/**
 * @summary Update Buyer
 * {@link /api/v1/buyer-roles/:role_id}
 */
export function updateBuyer<ThrowOnError extends boolean = true>(options: Options<UpdateBuyerOptions, ThrowOnError>): Promise<RequestResult<UpdateBuyerResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'PATCH', url: '/api/v1/buyer-roles/{role_id}', contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<UpdateBuyerResponses, ThrowOnError>>
}
