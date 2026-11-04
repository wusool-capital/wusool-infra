// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { HTTPValidationError } from './HTTPValidationError'
import type { RunDetailResponse } from './RunDetailResponse'

export type GetMatchRunPath = {
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  run_id: string;
};

export type GetMatchRunStatus200 = RunDetailResponse;

export type GetMatchRunStatus401 = ApiErrorResponse;

export type GetMatchRunStatus404 = ApiErrorResponse;

export type GetMatchRunStatus422 = HTTPValidationError;

export type GetMatchRunStatus503 = ApiErrorResponse;

export type GetMatchRunOptions = {
  body?: never;
  path: GetMatchRunPath;
  query?: never;
  headers?: never;
};

export type GetMatchRunResponses = {
  '200': GetMatchRunStatus200;
  '401': GetMatchRunStatus401;
  '404': GetMatchRunStatus404;
  '422': GetMatchRunStatus422;
  '503': GetMatchRunStatus503;
};

/**
 * @description Union of all possible responses
 */
export type GetMatchRunResponse = GetMatchRunStatus200;
