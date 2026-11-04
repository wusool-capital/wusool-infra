// @ts-nocheck

import * as z from 'zod'
import { contextReadingReadSchema } from './contextReadingReadSchema'
import { discrepancyReadSchema } from './discrepancyReadSchema'

export const preflightResponseSchema = z.object({
  buyer_role_id: z.string(),
  conflicts: z.array(discrepancyReadSchema),
  context: contextReadingReadSchema.describe('What the advisor\'s note was read as; amounts are absolute USD.'),
  context_checked: z.boolean(),
  missing: z.array(discrepancyReadSchema),
})
