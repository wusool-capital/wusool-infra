// @ts-nocheck

import type { SaveResearchOptions, SaveResearchResponses } from '../types/SaveResearch'
import type { Options, RequestResult } from '@/lib/api-client'
import { saveResearchResponseSchema, saveResearchErrorSchema } from '../zod/saveResearchSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Save Research
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/research/save}
 */
export function saveResearch<ThrowOnError extends boolean = true>(options: Options<SaveResearchOptions, ThrowOnError>): Promise<RequestResult<SaveResearchResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs/{run_id}/candidates/{candidate_id}/research/save', validator: { response: saveResearchResponseSchema, error: saveResearchErrorSchema }, contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<SaveResearchResponses, ThrowOnError>>
}
