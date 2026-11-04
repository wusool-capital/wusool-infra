// @ts-nocheck

import * as z from 'zod'

export const buyerCandidateOrgSchema = z.object({
  hq_country: z.union([z.string(), z.null()]).optional(),
  name: z.string(),
  sector_focus: z.array(z.string()).optional().default([]),
})
