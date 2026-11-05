// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { decisionResponseSchema } from './decisionResponseSchema'

export const startResearchPathRunIdSchema = z.uuid()

export const startResearchPathCandidateIdSchema = z.uuid()

export const startResearchStatus202Schema = decisionResponseSchema

export const startResearchStatus401Schema = apiErrorResponseSchema

export const startResearchStatus404Schema = apiErrorResponseSchema

export const startResearchStatus409Schema = apiErrorResponseSchema

export const startResearchStatus422Schema = HTTPValidationErrorSchema

export const startResearchStatus503Schema = apiErrorResponseSchema

export const startResearchResponseSchema = startResearchStatus202Schema

export const startResearchErrorSchema = z.union([startResearchStatus401Schema, startResearchStatus404Schema, startResearchStatus409Schema, startResearchStatus422Schema, startResearchStatus503Schema])

export const startResearchPathSchema = z.object({
  run_id: z.uuid(),
  candidate_id: z.uuid(),
})
