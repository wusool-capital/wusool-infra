// @ts-nocheck

import * as z from 'zod'

export const contextReadingReadSchema = z.object({
  countries: z.array(z.string()).default([]),
  ebitda_high: z.union([z.number(), z.null()]),
  ebitda_low: z.union([z.number(), z.null()]),
  ev_ceiling: z.union([z.number(), z.null()]),
  region: z.union([z.string(), z.null()]),
  revenue_high: z.union([z.number(), z.null()]),
  revenue_low: z.union([z.number(), z.null()]),
  seller_status: z.array(z.string()).default([]),
  ticket_high: z.union([z.number(), z.null()]),
  ticket_low: z.union([z.number(), z.null()]),
  verticals: z.array(z.string()).default([]),
}).describe('What the advisor\'s note was read as; amounts are absolute USD.')
