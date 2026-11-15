// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { ListBuyerRolesOptions, ListBuyerRolesResponses } from '../types/ListBuyerRoles'
import { client } from '../../lib/api-client'

/**
 * @summary List Buyer Roles
 * {@link /api/v1/buyer-roles}
 */
export function listBuyerRoles<ThrowOnError extends boolean = true>(options: Options<ListBuyerRolesOptions, ThrowOnError> = {}): Promise<RequestResult<ListBuyerRolesResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/buyer-roles', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<ListBuyerRolesResponses, ThrowOnError>>
}
