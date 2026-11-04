// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { HTTPValidationError } from './HTTPValidationError'
import type { RunDetailResponse } from './RunDetailResponse'

export type StartDiscoveryPath = {
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  run_id: string;
};

export type StartDiscoveryStatus202 = RunDetailResponse;

export type StartDiscoveryStatus401 = ApiErrorResponse;

export type StartDiscoveryStatus404 = ApiErrorResponse;

export type StartDiscoveryStatus422 = HTTPValidationError;

export type StartDiscoveryStatus503 = ApiErrorResponse;

export type StartDiscoveryOptions = {
  body?: never;
  path: StartDiscoveryPath;
  query?: never;
  headers?: never;
};

export type StartDiscoveryResponses = {
  '202': StartDiscoveryStatus202;
  '401': StartDiscoveryStatus401;
  '404': StartDiscoveryStatus404;
  '422': StartDiscoveryStatus422;
  '503': StartDiscoveryStatus503;
};

/**
 * @description Union of all possible responses
 */
export type StartDiscoveryResponse = StartDiscoveryStatus202;
