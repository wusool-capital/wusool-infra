// @ts-nocheck

import * as z from 'zod'

export const approveRequestSchema = z.object({
  existing_deal_id: z.union([z.string(), z.null()]).optional(),
  resolution: z.union([z.enum(['promote_existing', 'create_new']), z.null()]).optional(),
})
