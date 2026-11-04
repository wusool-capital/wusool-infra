// @ts-nocheck

import type { SkipResearchOptions, SkipResearchResponses } from '../types/SkipResearch'
import type { Options, RequestResult } from '@/lib/api-client'
import { skipResearchResponseSchema, skipResearchErrorSchema } from '../zod/skipResearchSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Skip Research
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/research/skip}
 */
export function skipResearch<ThrowOnError extends boolean = true>(options: Options<SkipResearchOptions, ThrowOnError>): Promise<RequestResult<SkipResearchResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs/{run_id}/candidates/{candidate_id}/research/skip', validator: { response: skipResearchResponseSchema, error: skipResearchErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<SkipResearchResponses, ThrowOnError>>
}
