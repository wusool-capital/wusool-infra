// @ts-nocheck

import * as z from 'zod'

export const moneyReadSchema = z.object({
  amount: z.number(),
  currency: z.string(),
})
