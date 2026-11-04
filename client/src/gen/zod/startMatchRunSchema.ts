// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { startRunRequestSchema } from './startRunRequestSchema'
import { startRunResponseSchema } from './startRunResponseSchema'

export const startMatchRunStatus202Schema = startRunResponseSchema

export const startMatchRunStatus401Schema = apiErrorResponseSchema

export const startMatchRunStatus404Schema = apiErrorResponseSchema

export const startMatchRunStatus422Schema = HTTPValidationErrorSchema

export const startMatchRunStatus503Schema = apiErrorResponseSchema

export const startMatchRunResponseSchema = startMatchRunStatus202Schema

export const startMatchRunErrorSchema = z.union([startMatchRunStatus401Schema, startMatchRunStatus404Schema, startMatchRunStatus422Schema, startMatchRunStatus503Schema])

export const startMatchRunBodySchema = startRunRequestSchema
