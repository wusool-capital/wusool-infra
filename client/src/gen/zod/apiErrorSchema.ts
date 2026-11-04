// @ts-nocheck

import * as z from 'zod'
import { existingDealReadSchema } from './existingDealReadSchema'

export const apiErrorSchema = z.object({
  code: z.enum(['unauthorized', 'web_disabled', 'not_found', 'already_reviewed', 'existing_deals', 'partial_write', 'run_not_ready', 'slack_sign_in_required', 'research_not_ready', 'research_busy', 'research_conflict', 'research_invalid']),
  existing_deals: z.array(existingDealReadSchema).default([]),
  fields: z.array(z.string()).default([]),
  message: z.string(),
})
