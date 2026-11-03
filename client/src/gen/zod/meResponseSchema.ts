// @ts-nocheck

import * as z from 'zod'

export const meResponseSchema = z.object({
  name: z.union([z.string(), z.null()]),
  slack_user_id: z.union([z.string(), z.null()]),
  via: z.enum(['slack', 'key']),
})
