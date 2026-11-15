// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { GetSellersUniverseOptions, GetSellersUniverseResponses } from '../types/GetSellersUniverse'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/views/sellers`
 * @summary Get Sellers Universe
 */
export function getSellersUniverse<ThrowOnError extends boolean = true>(options: Options<GetSellersUniverseOptions, ThrowOnError> = {}): Unwrappable<RequestResult<GetSellersUniverseResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<GetSellersUniverseResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/views/sellers', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
