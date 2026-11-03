// @ts-nocheck

import type { ApproveCandidateOptions, ApproveCandidateResponses } from '../types/ApproveCandidate'
import type { Options, RequestResult } from '@/lib/api-client'
import { approveCandidateResponseSchema, approveCandidateErrorSchema } from '../zod/approveCandidateSchema'
import { client } from '@/lib/api-client'

/**
 * @summary Approve Candidate
 * {@link /api/match-runs/:run_id/candidates/:candidate_id/approve}
 */
export function approveCandidate<ThrowOnError extends boolean = true>(options: Options<ApproveCandidateOptions, ThrowOnError>): Promise<RequestResult<ApproveCandidateResponses, ThrowOnError>> {
  const { client: request = client, ...config } = options

  return request({ method: 'POST', url: '/api/match-runs/{run_id}/candidates/{candidate_id}/approve', validator: { response: approveCandidateResponseSchema, error: approveCandidateErrorSchema }, contentType: { request: 'application/json' }, ...config, throwOnError: config.throwOnError ?? true }) as Promise<RequestResult<ApproveCandidateResponses, ThrowOnError>>
}
