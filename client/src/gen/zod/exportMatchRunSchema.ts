// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'

export const exportMatchRunPathRunIdSchema = z.uuid()

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
