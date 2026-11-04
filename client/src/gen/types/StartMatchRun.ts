// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { HTTPValidationError } from './HTTPValidationError'
import type { StartRunRequest } from './StartRunRequest'
import type { StartRunResponse } from './StartRunResponse'

export type StartMatchRunStatus202 = StartRunResponse;

export type StartMatchRunStatus401 = ApiErrorResponse;

export type StartMatchRunStatus404 = ApiErrorResponse;

export type StartMatchRunStatus422 = HTTPValidationError;

export type StartMatchRunStatus503 = ApiErrorResponse;

export type StartMatchRunBody = StartRunRequest;

export type StartMatchRunOptions = {
  body: StartMatchRunBody;
  path?: never;
  query?: never;
  headers?: never;
};

export type StartMatchRunResponses = {
  '202': StartMatchRunStatus202;
  '401': StartMatchRunStatus401;
  '404': StartMatchRunStatus404;
  '422': StartMatchRunStatus422;
  '503': StartMatchRunStatus503;
};

/**
 * @description Union of all possible responses
 */
export type StartMatchRunResponse = StartMatchRunStatus202;
