// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { GetCurrentUserOptions, GetCurrentUserResponses } from '../types/GetCurrentUser'
import { client } from '../../lib/api-client'

/**
 * @summary Get Me
 * {@link /api/v1/me}
 */
export function getCurrentUser<ThrowOnError extends boolean = true>(options: Options<GetCurrentUserOptions, ThrowOnError> = {}): Promise<RequestResult<GetCurrentUserResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/me', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetCurrentUserResponses, ThrowOnError>>
}
