// @ts-nocheck

import * as z from 'zod'
import { researchJobChangeReadSchema } from './researchJobChangeReadSchema'
import { researchPostReadSchema } from './researchPostReadSchema'

export const researchLinkedInReadSchema = z.object({
  contacts_without_linkedin: z.int(),
  job_changes: z.array(researchJobChangeReadSchema),
  outcome: z.enum(['completed', 'skipped', 'failed']),
  posts: z.array(researchPostReadSchema),
})
