// @ts-nocheck

import * as z from 'zod'

export const preflightRequestSchema = z.object({
  advisor_context: z.union([z.string().max(4000), z.null()]).optional(),
})
