// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { UpdateSellerOptions, UpdateSellerResponses } from '../types/UpdateSeller'
import { client } from '../../lib/api-client'

/**
 * @summary Update Seller
 * {@link /api/v1/seller-roles/:role_id}
 */
export function updateSeller<ThrowOnError extends boolean = true>(options: Options<UpdateSellerOptions, ThrowOnError>): Promise<RequestResult<UpdateSellerResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'PATCH', url: '/api/v1/seller-roles/{role_id}', contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<UpdateSellerResponses, ThrowOnError>>
}
