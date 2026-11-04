// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { runDetailResponseSchema } from './runDetailResponseSchema'

export const getMatchRunPathRunIdSchema = z.uuid()

export const getMatchRunStatus200Schema = runDetailResponseSchema

export const getMatchRunStatus401Schema = apiErrorResponseSchema

export const getMatchRunStatus404Schema = apiErrorResponseSchema

export const getMatchRunStatus422Schema = HTTPValidationErrorSchema

export const getMatchRunStatus503Schema = apiErrorResponseSchema

export const getMatchRunResponseSchema = getMatchRunStatus200Schema

export const getMatchRunErrorSchema = z.union([getMatchRunStatus401Schema, getMatchRunStatus404Schema, getMatchRunStatus422Schema, getMatchRunStatus503Schema])

export const getMatchRunPathSchema = z.object({
  run_id: z.uuid(),
})
