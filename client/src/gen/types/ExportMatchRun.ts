// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { HTTPValidationError } from './HTTPValidationError'

export type ExportMatchRunPath = {
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  run_id: string;
};

export type ExportMatchRunStatus200 = Blob;

export type ExportMatchRunStatus401 = ApiErrorResponse;

export type ExportMatchRunStatus404 = ApiErrorResponse;

export type ExportMatchRunStatus422 = HTTPValidationError;

export type ExportMatchRunStatus503 = ApiErrorResponse;

export type ExportMatchRunOptions = {
  body?: never;
  path: ExportMatchRunPath;
  query?: never;
  headers?: never;
};

export type ExportMatchRunResponses = {
  '200': ExportMatchRunStatus200;
  '401': ExportMatchRunStatus401;
  '404': ExportMatchRunStatus404;
  '422': ExportMatchRunStatus422;
  '503': ExportMatchRunStatus503;
};

/**
 * @description Union of all possible responses
 */
export type ExportMatchRunResponse = ExportMatchRunStatus200;
