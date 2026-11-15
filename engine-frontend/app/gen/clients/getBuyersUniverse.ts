// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { GetBuyersUniverseOptions, GetBuyersUniverseResponses } from '../types/GetBuyersUniverse'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/views/buyers`
 * @summary Get Buyers Universe
 */
export function getBuyersUniverse<ThrowOnError extends boolean = true>(options: Options<GetBuyersUniverseOptions, ThrowOnError> = {}): Unwrappable<RequestResult<GetBuyersUniverseResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<GetBuyersUniverseResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/views/buyers', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
