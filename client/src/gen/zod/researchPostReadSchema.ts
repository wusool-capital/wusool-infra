// @ts-nocheck

import * as z from 'zod'

export const researchPostReadSchema = z.object({
  author_name: z.union([z.string(), z.null()]),
  posted_at: z.union([z.iso.datetime(), z.null()]),
  text: z.string(),
  url: z.string(),
})
