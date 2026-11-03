// @ts-nocheck

import * as z from 'zod'
import { candidateReadSchema } from './candidateReadSchema'
import { discoveryReadSchema } from './discoveryReadSchema'

export const runDetailResponseSchema = z.object({
  buyer_org_name: z.string(),
  buyer_role_id: z.string(),
  candidates: z.array(candidateReadSchema),
  candidates_considered: z.union([z.int(), z.null()]),
  candidates_filtered: z.union([z.int(), z.null()]),
  completed_at: z.union([z.iso.datetime(), z.null()]),
  discovery: discoveryReadSchema,
  discovery_threshold: z.number(),
  error: z.union([z.string(), z.null()]),
  low_match_quality: z.boolean(),
  notes: z.array(z.string()),
  run_id: z.uuid(),
  started_at: z.iso.datetime(),
  state: z.enum(['running', 'stale', 'failed', 'completed']),
})
