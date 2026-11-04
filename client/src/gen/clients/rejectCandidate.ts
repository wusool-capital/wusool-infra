// @ts-nocheck

import type { RejectCandidateOptions, RejectCandidateResponses } from '../types/RejectCandidate'
import type { Options, RequestResult } from '@/lib/api-client'
import { rejectCandidateResponseSchema, rejectCandidateErrorSchema } from '../zod/rejectCandidateSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Reject Candidate
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/reject}
 */
export function rejectCandidate<ThrowOnError extends boolean = true>(options: Options<RejectCandidateOptions, ThrowOnError>): Promise<RequestResult<RejectCandidateResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs/{run_id}/candidates/{candidate_id}/reject', validator: { response: rejectCandidateResponseSchema, error: rejectCandidateErrorSchema }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<RejectCandidateResponses, ThrowOnError>>
}
