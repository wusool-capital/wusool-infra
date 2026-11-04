// @ts-nocheck

import type { SearchBuyersOptions, SearchBuyersResponses } from '../types/SearchBuyers'
import type { Options, RequestResult } from '@/lib/api-client'
import { searchBuyersResponseSchema, searchBuyersErrorSchema } from '../zod/searchBuyersSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Search Buyers
 * {@link /api/buyers}
 */
export function searchBuyers<ThrowOnError extends boolean = true>(options: Options<SearchBuyersOptions, ThrowOnError>): Promise<RequestResult<SearchBuyersResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/buyers', validator: { response: searchBuyersResponseSchema, error: searchBuyersErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<SearchBuyersResponses, ThrowOnError>>
}
