// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { decisionResponseSchema } from './decisionResponseSchema'

export const rejectCandidatePathRunIdSchema = z.uuid()

export const rejectCandidatePathCandidateIdSchema = z.uuid()

export const rejectCandidateStatus200Schema = decisionResponseSchema

export const rejectCandidateStatus401Schema = apiErrorResponseSchema

export const rejectCandidateStatus404Schema = apiErrorResponseSchema

export const rejectCandidateStatus409Schema = apiErrorResponseSchema

export const rejectCandidateStatus422Schema = HTTPValidationErrorSchema

export const rejectCandidateStatus503Schema = apiErrorResponseSchema

export const rejectCandidateResponseSchema = rejectCandidateStatus200Schema

export const rejectCandidateErrorSchema = z.union([rejectCandidateStatus401Schema, rejectCandidateStatus404Schema, rejectCandidateStatus409Schema, rejectCandidateStatus422Schema, rejectCandidateStatus503Schema])

export const rejectCandidatePathSchema = z.object({
  run_id: z.uuid(),
  candidate_id: z.uuid(),
})
