// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { preflightRequestSchema } from './preflightRequestSchema'
import { preflightResponseSchema } from './preflightResponseSchema'

export const preflightPathBuyerRoleIdSchema = z.uuid()

export const preflightStatus200Schema = preflightResponseSchema

export const preflightStatus401Schema = apiErrorResponseSchema

export const preflightStatus404Schema = apiErrorResponseSchema

export const preflightStatus422Schema = HTTPValidationErrorSchema

export const preflightStatus503Schema = apiErrorResponseSchema

export const preflightResponseSchema2 = preflightStatus200Schema

export const preflightErrorSchema = z.union([preflightStatus401Schema, preflightStatus404Schema, preflightStatus422Schema, preflightStatus503Schema])

export const preflightBodySchema = preflightRequestSchema

export const preflightPathSchema = z.object({
  buyer_role_id: z.uuid(),
})
