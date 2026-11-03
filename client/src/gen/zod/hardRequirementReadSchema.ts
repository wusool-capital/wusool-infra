// @ts-nocheck

import * as z from 'zod'

export const hardRequirementReadSchema = z.object({
  criterion: z.string(),
  human_confirmed: z.boolean(),
  source: z.string(),
  value: z.union([z.string(), z.null()]),
})
