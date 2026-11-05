// @ts-nocheck

import * as z from 'zod'

export const saveResearchRequestSchema = z.object({
  fields: z.array(z.string()).min(1),
})
