// @ts-nocheck

import * as z from 'zod'

export const discoveryReadSchema = z.object({
  message: z.union([z.string(), z.null()]),
  notes: z.array(z.string()).default([]),
  status: z.enum(['not_needed', 'available', 'running', 'done', 'skipped', 'unavailable', 'failed']),
})
