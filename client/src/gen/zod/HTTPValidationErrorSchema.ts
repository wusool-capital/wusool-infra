// @ts-nocheck

import * as z from 'zod'
import { validationErrorSchema } from './validationErrorSchema'

export const HTTPValidationErrorSchema = z.object({
  detail: z.array(validationErrorSchema).optional(),
})
