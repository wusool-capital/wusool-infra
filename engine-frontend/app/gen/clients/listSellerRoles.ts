// @ts-nocheck

import type { Options, RequestResult } from '../../lib/api-client'
import type { ListSellerRolesOptions, ListSellerRolesResponses } from '../types/ListSellerRoles'
import { client } from '../../lib/api-client'

/**
 * @summary List Seller Roles
 * {@link /api/v1/seller-roles}
 */
export function listSellerRoles<ThrowOnError extends boolean = true>(options: Options<ListSellerRolesOptions, ThrowOnError> = {}): Promise<RequestResult<ListSellerRolesResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'GET', url: '/api/v1/seller-roles', ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<ListSellerRolesResponses, ThrowOnError>>
}
