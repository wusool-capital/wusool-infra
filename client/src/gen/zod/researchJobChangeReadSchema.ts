// @ts-nocheck

import * as z from 'zod'

export const researchJobChangeReadSchema = z.object({
  company: z.union([z.string(), z.null()]),
  name: z.string(),
  source_url: z.string(),
  title: z.union([z.string(), z.null()]),
})
