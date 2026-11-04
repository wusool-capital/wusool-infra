// @ts-nocheck

import { authConfigResponseSchema } from './authConfigResponseSchema'

export const getAuthConfigStatus200Schema = authConfigResponseSchema.describe('Which sign-in methods the page should offer.')

export const getAuthConfigResponseSchema = getAuthConfigStatus200Schema
