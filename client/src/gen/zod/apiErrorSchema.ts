// @ts-nocheck

import * as z from 'zod'
import { existingDealReadSchema } from './existingDealReadSchema'

export const apiErrorSchema = z.object({
  code: z.enum(['unauthorized', 'web_disabled', 'not_found', 'already_reviewed', 'existing_deals', 'partial_write', 'run_not_ready']),
  existing_deals: z.array(existingDealReadSchema).default([]),
  message: z.string(),
})
