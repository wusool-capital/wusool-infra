// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { GetSellersUniverseOptions, GetSellersUniverseResponses } from '../types/GetSellersUniverse'
import { client } from '../../lib/api-client'

/**
 * @summary Get Sellers Universe
 * {@link /api/v1/views/sellers}
 */
export function getSellersUniverse<ThrowOnError extends boolean = true>(options: Options<GetSellersUniverseOptions, ThrowOnError> = {}): Promise<RequestResult<GetSellersUniverseResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/views/sellers', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetSellersUniverseResponses, ThrowOnError>>
}
