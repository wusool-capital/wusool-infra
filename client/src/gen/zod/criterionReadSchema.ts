// @ts-nocheck

import * as z from 'zod'

export const criterionReadSchema = z.object({
  criterion: z.string(),
  criterion_type: z.enum(['hard', 'soft']),
  data_backing: z.string(),
  result: z.string(),
})
