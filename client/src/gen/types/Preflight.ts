// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { HTTPValidationError } from './HTTPValidationError'
import type { PreflightRequest } from './PreflightRequest'
import type { PreflightResponse } from './PreflightResponse'

export type PreflightPath = {
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  buyer_role_id: string;
};

export type PreflightStatus200 = PreflightResponse;

export type PreflightStatus401 = ApiErrorResponse;

export type PreflightStatus404 = ApiErrorResponse;

export type PreflightStatus422 = HTTPValidationError;

export type PreflightStatus503 = ApiErrorResponse;

export type PreflightBody = PreflightRequest;

export type PreflightOptions = {
  body: PreflightBody;
  path: PreflightPath;
  query?: never;
  headers?: never;
};

export type PreflightResponses = {
  '200': PreflightStatus200;
  '401': PreflightStatus401;
  '404': PreflightStatus404;
  '422': PreflightStatus422;
  '503': PreflightStatus503;
};

/**
 * @description Union of all possible responses
 */
export type PreflightResponse2 = PreflightStatus200;
