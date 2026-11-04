// @ts-nocheck

import * as z from 'zod'
import { HTTPValidationErrorSchema } from './HTTPValidationErrorSchema'
import { apiErrorResponseSchema } from './apiErrorResponseSchema'
import { runDetailResponseSchema } from './runDetailResponseSchema'

export const startDiscoveryPathRunIdSchema = z.uuid()

export const startDiscoveryStatus202Schema = runDetailResponseSchema

export const startDiscoveryStatus401Schema = apiErrorResponseSchema

export const startDiscoveryStatus404Schema = apiErrorResponseSchema

export const startDiscoveryStatus422Schema = HTTPValidationErrorSchema

export const startDiscoveryStatus503Schema = apiErrorResponseSchema

export const startDiscoveryResponseSchema = startDiscoveryStatus202Schema

export const startDiscoveryErrorSchema = z.union([startDiscoveryStatus401Schema, startDiscoveryStatus404Schema, startDiscoveryStatus422Schema, startDiscoveryStatus503Schema])

export const startDiscoveryPathSchema = z.object({
  run_id: z.uuid(),
})
