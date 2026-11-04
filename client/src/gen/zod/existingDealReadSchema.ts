// @ts-nocheck

import * as z from 'zod'

export const existingDealReadSchema = z.object({
  attio_id: z.string(),
  name: z.string(),
  stage: z.union([z.string(), z.null()]),
  web_url: z.union([z.string(), z.null()]),
})
