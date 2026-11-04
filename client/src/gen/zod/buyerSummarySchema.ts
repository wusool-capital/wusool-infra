// @ts-nocheck

import * as z from 'zod'
import { buyerCandidateOrgSchema } from './buyerCandidateOrgSchema'

export const buyerSummarySchema = z.object({
  id: z.string(),
  mandate_status: z.union([z.string(), z.null()]).optional(),
  model: z.union([z.string(), z.null()]).optional(),
  organization: buyerCandidateOrgSchema,
  target_vertical: z.union([z.string(), z.null()]).optional(),
})
