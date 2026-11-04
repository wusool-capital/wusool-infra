// @ts-nocheck

import * as z from 'zod'

export const researchFieldReadSchema = z.object({
  confidence: z.number(),
  display: z.string(),
  name: z.string(),
  rationale: z.string(),
  saved: z.boolean(),
  source_url: z.string(),
  target: z.enum(['organization', 'seller_role']),
})
