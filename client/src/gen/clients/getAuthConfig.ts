// @ts-nocheck

import type { GetAuthConfigOptions, GetAuthConfigResponses } from '../types/GetAuthConfig'
import type { Options, RequestResult } from '@/lib/api-client'
import { getAuthConfigResponseSchema } from '../zod/getAuthConfigSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Get Auth Config
 * {@link /api/auth/config}
 */
export function getAuthConfig<ThrowOnError extends boolean = true>(options: Options<GetAuthConfigOptions, ThrowOnError> = {}): Promise<RequestResult<GetAuthConfigResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/auth/config', validator: { response: getAuthConfigResponseSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetAuthConfigResponses, ThrowOnError>>
}
