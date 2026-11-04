// @ts-nocheck

import * as z from 'zod'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { decisionResponseSchema } from './decisionResponseSchema'
import { saveResearchRequestSchema } from './saveResearchRequestSchema'

export const saveResearchPathRunIdSchema = z.uuid()

export const saveResearchPathCandidateIdSchema = z.uuid()

export const saveResearchStatus200Schema = decisionResponseSchema

export const saveResearchStatus401Schema = apiErrorResponseSchema

export const saveResearchStatus403Schema = apiErrorResponseSchema

export const saveResearchStatus404Schema = apiErrorResponseSchema

export const saveResearchStatus409Schema = apiErrorResponseSchema

export const saveResearchStatus422Schema = apiErrorResponseSchema

export const saveResearchStatus502Schema = apiErrorResponseSchema

export const saveResearchStatus503Schema = apiErrorResponseSchema

export const saveResearchResponseSchema = saveResearchStatus200Schema

export const saveResearchErrorSchema = z.union([saveResearchStatus401Schema, saveResearchStatus403Schema, saveResearchStatus404Schema, saveResearchStatus409Schema, saveResearchStatus422Schema, saveResearchStatus502Schema, saveResearchStatus503Schema])

export const saveResearchBodySchema = saveResearchRequestSchema

export const saveResearchPathSchema = z.object({
  run_id: z.uuid(),
  candidate_id: z.uuid(),
})
