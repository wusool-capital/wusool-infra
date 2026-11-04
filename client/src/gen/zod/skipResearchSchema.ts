// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { decisionResponseSchema } from './decisionResponseSchema'

export const skipResearchPathRunIdSchema = z.uuid()

export const skipResearchPathCandidateIdSchema = z.uuid()

export const skipResearchStatus200Schema = decisionResponseSchema

export const skipResearchStatus401Schema = apiErrorResponseSchema

export const skipResearchStatus404Schema = apiErrorResponseSchema

export const skipResearchStatus409Schema = apiErrorResponseSchema

export const skipResearchStatus422Schema = HTTPValidationErrorSchema

export const skipResearchStatus503Schema = apiErrorResponseSchema

export const skipResearchResponseSchema = skipResearchStatus200Schema

export const skipResearchErrorSchema = z.union([skipResearchStatus401Schema, skipResearchStatus404Schema, skipResearchStatus409Schema, skipResearchStatus422Schema, skipResearchStatus503Schema])

export const skipResearchPathSchema = z.object({
  run_id: z.uuid(),
  candidate_id: z.uuid(),
})
