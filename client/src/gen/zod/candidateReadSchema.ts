// @ts-nocheck

import * as z from 'zod'

export const candidateReadSchema = z.object({
  data_confidence: z.union([z.number(), z.null()]),
  deal_attio_id: z.union([z.string(), z.null()]),
  decided_at: z.union([z.iso.datetime(), z.null()]),
  decision: z.union([z.string(), z.null()]),
  id: z.uuid(),
  match_score: z.union([z.number(), z.null()]),
  origin: z.enum(['crm', 'discovery']),
  rank: z.int(),
  recommended_pitch: z.union([z.string(), z.null()]),
  risks_and_gaps: z.union([z.string(), z.null()]),
  seller_attio_id: z.union([z.string(), z.null()]),
  seller_org_name: z.string(),
  source_url: z.union([z.string(), z.null()]),
  status: z.string(),
  why_chosen_over_alternatives: z.union([z.string(), z.null()]),
  why_it_matches: z.union([z.string(), z.null()]),
})
