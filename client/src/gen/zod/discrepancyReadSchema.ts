// @ts-nocheck

import * as z from 'zod'

export const discrepancyReadSchema = z.object({
  criterion: z.enum(['vertical', 'geography', 'ticket_band', 'ebitda']),
  stated: z.union([z.string(), z.null()]),
  stored: z.string(),
})
