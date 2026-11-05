// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { DecisionResponse } from './DecisionResponse'
import type { HTTPValidationError } from './HTTPValidationError'

export type StartResearchPath = {
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  run_id: string;
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  candidate_id: string;
};

export type StartResearchStatus202 = DecisionResponse;

export type StartResearchStatus401 = ApiErrorResponse;

export type StartResearchStatus404 = ApiErrorResponse;

export type StartResearchStatus409 = ApiErrorResponse;

export type StartResearchStatus422 = HTTPValidationError;

export type StartResearchStatus503 = ApiErrorResponse;

export type StartResearchOptions = {
  body?: never;
  path: StartResearchPath;
  query?: never;
  headers?: never;
};

export type StartResearchResponses = {
  '202': StartResearchStatus202;
  '401': StartResearchStatus401;
  '404': StartResearchStatus404;
  '409': StartResearchStatus409;
  '422': StartResearchStatus422;
  '503': StartResearchStatus503;
};

/**
 * @description Union of all possible responses
 */
export type StartResearchResponse = StartResearchStatus202;
