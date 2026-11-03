// @ts-nocheck

import * as z from 'zod'
import { candidateReadSchema } from './candidateReadSchema'

export const decisionResponseSchema = z.object({
  candidate: candidateReadSchema,
  research_channel_id: z.union([z.string(), z.null()]),
})
