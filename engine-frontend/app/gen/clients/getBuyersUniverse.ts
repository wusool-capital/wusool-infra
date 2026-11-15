// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { GetBuyersUniverseOptions, GetBuyersUniverseResponses } from '../types/GetBuyersUniverse'
import { client } from '../../lib/api-client'

/**
 * @summary Get Buyers Universe
 * {@link /api/v1/views/buyers}
 */
export function getBuyersUniverse<ThrowOnError extends boolean = true>(options: Options<GetBuyersUniverseOptions, ThrowOnError> = {}): Promise<RequestResult<GetBuyersUniverseResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/views/buyers', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetBuyersUniverseResponses, ThrowOnError>>
}
