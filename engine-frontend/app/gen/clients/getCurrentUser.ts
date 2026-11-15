// @ts-nocheck

import type { Options, Unwrappable, RequestResult } from '../.kubb/client'
import type { GetCurrentUserOptions, GetCurrentUserResponses } from '../types/GetCurrentUser'
import { client, withUnwrap, resolveThrowOnError } from '../.kubb/client'

/**
 * `GET /api/v1/me`
 * @summary Get Me
 */
export function getCurrentUser<ThrowOnError extends boolean = true>(options: Options<GetCurrentUserOptions, ThrowOnError> = {}): Unwrappable<RequestResult<GetCurrentUserResponses, ThrowOnError>> {
  const { client: apiClient = client, ...config } = options

  return withUnwrap(apiClient<GetCurrentUserResponses, ThrowOnError>({ method: 'GET', url: '/api/v1/me', ...config, throwOnError: resolveThrowOnError(config.throwOnError, true) }))
}
