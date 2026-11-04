// @ts-nocheck

import * as z from 'zod'
import { apiErrorSchema } from './apiErrorSchema'

export const apiErrorResponseSchema = z.object({
  detail: apiErrorSchema,
})
