// @ts-nocheck

import * as z from 'zod'
import { researchFieldReadSchema } from './researchFieldReadSchema'
import { researchLinkedInReadSchema } from './researchLinkedInReadSchema'

export const researchReadSchema = z.object({
  error: z.union([z.string(), z.null()]),
  fields: z.array(researchFieldReadSchema),
  linkedin: z.union([researchLinkedInReadSchema, z.null()]),
  reviewed: z.boolean(),
  started_at: z.iso.datetime(),
  status: z.enum(['running', 'done', 'failed']),
}).describe('Full research on an approved discovered seller, for review in the page.')
