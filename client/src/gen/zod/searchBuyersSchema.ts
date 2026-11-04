// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { buyerSummarySchema } from './buyerSummarySchema'

export const searchBuyersQueryQSchema = z.string().min(2).max(200)

export const searchBuyersStatus200Schema = z.array(buyerSummarySchema)

export const searchBuyersStatus401Schema = apiErrorResponseSchema

export const searchBuyersStatus404Schema = apiErrorResponseSchema

export const searchBuyersStatus422Schema = HTTPValidationErrorSchema

export const searchBuyersStatus503Schema = apiErrorResponseSchema

export const searchBuyersResponseSchema = searchBuyersStatus200Schema

export const searchBuyersErrorSchema = z.union([searchBuyersStatus401Schema, searchBuyersStatus404Schema, searchBuyersStatus422Schema, searchBuyersStatus503Schema])

export const searchBuyersQuerySchema = z.object({
  q: z.string().min(2).max(200),
})
