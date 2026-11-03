// @ts-nocheck

import type { LogoutStatus204 } from '../types/Logout'
import type { RequestConfig, ResponseErrorConfig } from '@/lib/api-client'
import type { UseMutationOptions, UseMutationResult, QueryClient } from '@tanstack/react-query'
import { logout } from '../clients/logout'
import { mutationOptions, useMutation } from '@tanstack/react-query'

export const logoutMutationKey = () => [{ url: '/api/auth/logout' }] as const

export function logoutMutationOptions<TContext = unknown>(config: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>> = {}) {
  const mutationKey = logoutMutationKey()
  return mutationOptions<LogoutStatus204, ResponseErrorConfig<Error>, undefined, TContext>({
    mutationKey,
    mutationFn: async(_) => {
      return (await logout({ ...config, throwOnError: true })).data
    },
  })
}

/**
 * @summary Logout
 * {@link /api/auth/logout}
 */
export function useLogout<TContext>(options: {
  mutation?: UseMutationOptions<LogoutStatus204, ResponseErrorConfig<Error>, undefined, TContext> & { client?: QueryClient },
  client?: Partial<Omit<RequestConfig, 'path' | 'query' | 'body' | 'headers' | 'url'>>,
} = {}) {
  const { mutation = {}, client: config = {} } = options ?? {}
  const { client: queryClient, ...mutationOptions } = mutation;
  const mutationKey = mutationOptions.mutationKey ?? logoutMutationKey()

  const baseOptions = logoutMutationOptions(config) as UseMutationOptions<LogoutStatus204, ResponseErrorConfig<Error>, undefined, TContext>

  return useMutation<LogoutStatus204, ResponseErrorConfig<Error>, undefined, TContext>({
    ...baseOptions,
    mutationKey,
    ...mutationOptions,
  }, queryClient) as UseMutationResult<LogoutStatus204, ResponseErrorConfig<Error>, undefined, TContext>
}
