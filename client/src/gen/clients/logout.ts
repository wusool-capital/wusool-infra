// @ts-nocheck

import type { LogoutOptions, LogoutResponses } from '../types/Logout'
import type { Options, RequestResult } from '@/lib/api-client'
import { logoutResponseSchema } from '../zod/logoutSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Logout
 * {@link /api/auth/logout}
 */
export function logout<ThrowOnError extends boolean = true>(options: Options<LogoutOptions, ThrowOnError> = {}): Promise<RequestResult<LogoutResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/auth/logout', validator: { response: logoutResponseSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<LogoutResponses, ThrowOnError>>
}
