// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { approveRequestSchema } from './approveRequestSchema'
import { decisionResponseSchema } from './decisionResponseSchema'

export const approveCandidatePathRunIdSchema = z.uuid()

export const approveCandidatePathCandidateIdSchema = z.uuid()

export const approveCandidateStatus200Schema = decisionResponseSchema

export const approveCandidateStatus401Schema = apiErrorResponseSchema

export const approveCandidateStatus404Schema = apiErrorResponseSchema

export const approveCandidateStatus409Schema = apiErrorResponseSchema

export const approveCandidateStatus422Schema = HTTPValidationErrorSchema

export const approveCandidateStatus502Schema = apiErrorResponseSchema

export const approveCandidateStatus503Schema = apiErrorResponseSchema

export const approveCandidateResponseSchema = approveCandidateStatus200Schema

export const approveCandidateErrorSchema = z.union([approveCandidateStatus401Schema, approveCandidateStatus404Schema, approveCandidateStatus409Schema, approveCandidateStatus422Schema, approveCandidateStatus502Schema, approveCandidateStatus503Schema])

export const approveCandidateBodySchema = approveRequestSchema

export const approveCandidatePathSchema = z.object({
  run_id: z.uuid(),
  candidate_id: z.uuid(),
})
