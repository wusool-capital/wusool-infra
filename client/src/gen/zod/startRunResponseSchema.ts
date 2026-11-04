// @ts-nocheck

import * as z from 'zod'

export const startRunResponseSchema = z.object({
  run_id: z.uuid(),
})
