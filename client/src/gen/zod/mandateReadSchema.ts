// @ts-nocheck

import * as z from 'zod'
import { hardRequirementReadSchema } from './hardRequirementReadSchema'

export const mandateReadSchema = z.object({
  hard_requirements: z.array(hardRequirementReadSchema),
  ideal_target: z.union([z.string(), z.null()]),
  strategic_thesis: z.union([z.string(), z.null()]),
}).describe('Slack\'s "Buyer & Mandate" section of View Full Analysis.')
