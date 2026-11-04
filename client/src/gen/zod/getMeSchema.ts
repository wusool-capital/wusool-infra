// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { meResponseSchema } from './meResponseSchema'

export const getMeStatus200Schema = meResponseSchema

export const getMeStatus401Schema = apiErrorResponseSchema

export const getMeStatus422Schema = HTTPValidationErrorSchema

export const getMeResponseSchema = getMeStatus200Schema

export const getMeErrorSchema = z.union([getMeStatus401Schema, getMeStatus422Schema])
