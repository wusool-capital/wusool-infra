// @ts-nocheck

import type { StartResearchOptions, StartResearchResponses } from '../types/StartResearch'
import type { Options, RequestResult } from '@/lib/api-client'
import { startResearchResponseSchema, startResearchErrorSchema } from '../zod/startResearchSchema'
import { client } from '@/lib/api-client'

/**
 * @description Starts or retries the research; the claim makes a repeat a no-op.
 * @summary Start Research
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/research}
 */
export function startResearch<ThrowOnError extends boolean = true>(options: Options<StartResearchOptions, ThrowOnError>): Promise<RequestResult<StartResearchResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs/{run_id}/candidates/{candidate_id}/research', validator: { response: startResearchResponseSchema, error: startResearchErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<StartResearchResponses, ThrowOnError>>
}
