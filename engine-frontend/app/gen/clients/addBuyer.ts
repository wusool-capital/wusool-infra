// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { AddBuyerOptions, AddBuyerResponses } from '../types/AddBuyer'
import { client } from '../../lib/api-client'

/**
 * @summary Add Buyer
 * {@link /api/v1/buyer-roles}
 */
export function addBuyer<ThrowOnError extends boolean = true>(options: Options<AddBuyerOptions, ThrowOnError>): Promise<RequestResult<AddBuyerResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/v1/buyer-roles', contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<AddBuyerResponses, ThrowOnError>>
}
