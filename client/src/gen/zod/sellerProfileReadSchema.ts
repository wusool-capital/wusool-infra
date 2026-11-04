// @ts-nocheck

import * as z from 'zod'
import { moneyReadSchema } from './moneyReadSchema'

export const sellerProfileReadSchema = z.object({
  description: z.union([z.string(), z.null()]),
  employee_range: z.union([z.string(), z.null()]),
  est_ebitda: z.union([moneyReadSchema, z.null()]),
  est_revenue: z.union([moneyReadSchema, z.null()]),
  founded_year: z.union([z.int(), z.null()]),
  hq_country: z.union([z.string(), z.null()]),
  location_count: z.union([z.int(), z.null()]),
  sector_focus: z.array(z.string()),
  website: z.union([z.string(), z.null()]),
})
