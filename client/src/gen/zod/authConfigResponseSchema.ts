// @ts-nocheck

import * as z from 'zod'

export const authConfigResponseSchema = z.object({
  api_key: z.boolean(),
  slack_sign_in: z.boolean(),
}).describe('Which sign-in methods the page should offer.')
