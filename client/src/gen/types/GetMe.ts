// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { HTTPValidationError } from './HTTPValidationError'
import type { MeResponse } from './MeResponse'

export type GetMeStatus200 = MeResponse;

export type GetMeStatus401 = ApiErrorResponse;

export type GetMeStatus422 = HTTPValidationError;

export type GetMeOptions = {
  body?: never;
  path?: never;
  query?: never;
  headers?: never;
};

export type GetMeResponses = {
  '200': GetMeStatus200;
  '401': GetMeStatus401;
  '422': GetMeStatus422;
};

/**
 * @description Union of all possible responses
 */
export type GetMeResponse = GetMeStatus200;
