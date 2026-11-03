// @ts-nocheck

import * as z from 'zod'

export const validationErrorSchema = z.object({
  ctx: z.object({}).optional(),
  input: z.unknown().optional(),
  loc: z.array(z.union([z.string(), z.int()])),
  msg: z.string(),
  type: z.string(),
})
