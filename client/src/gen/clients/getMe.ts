// @ts-nocheck

import type { GetMeOptions, GetMeResponses } from '../types/GetMe'
import type { Options, RequestResult } from '@/lib/api-client'
import { getMeResponseSchema, getMeErrorSchema } from '../zod/getMeSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Get Me
 * {@link /api/auth/me}
 */
export function getMe<ThrowOnError extends boolean = true>(options: Options<GetMeOptions, ThrowOnError> = {}): Promise<RequestResult<GetMeResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/auth/me', validator: { response: getMeResponseSchema, error: getMeErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<GetMeResponses, ThrowOnError>>
}
