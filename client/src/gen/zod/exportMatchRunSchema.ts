// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'

export const exportMatchRunPathRunIdSchema = z.uuid()

export const exportMatchRunQueryFieldsSchema = z.union([z.array(z.enum(['rank', 'origin', 'seller', 'seller_attio_id', 'match_score', 'data_confidence', 'status', 'why_it_matches', 'why_chosen_over_alternatives', 'recommended_pitch', 'risks_and_gaps', 'source_url'])), z.null()]).optional()

export const exportMatchRunStatus200Schema = z.instanceof(File)

export const exportMatchRunStatus401Schema = apiErrorResponseSchema

export const exportMatchRunStatus404Schema = apiErrorResponseSchema

export const exportMatchRunStatus422Schema = HTTPValidationErrorSchema

export const exportMatchRunStatus503Schema = apiErrorResponseSchema

export const exportMatchRunResponseSchema = exportMatchRunStatus200Schema

export const exportMatchRunErrorSchema = z.union([exportMatchRunStatus401Schema, exportMatchRunStatus404Schema, exportMatchRunStatus422Schema, exportMatchRunStatus503Schema])

export const exportMatchRunPathSchema = z.object({
  run_id: z.uuid(),
})

export const exportMatchRunQuerySchema = z.object({
  fields: z.union([z.array(z.enum(['rank', 'origin', 'seller', 'seller_attio_id', 'match_score', 'data_confidence', 'status', 'why_it_matches', 'why_chosen_over_alternatives', 'recommended_pitch', 'risks_and_gaps', 'source_url'])), z.null()]).optional(),
})
