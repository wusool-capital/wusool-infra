// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { DecisionResponse } from './DecisionResponse'
import type { HTTPValidationError } from './HTTPValidationError'

export type SkipResearchPath = {
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

export type SkipResearchStatus200 = DecisionResponse;

export type SkipResearchStatus401 = ApiErrorResponse;

export type SkipResearchStatus404 = ApiErrorResponse;

export type SkipResearchStatus409 = ApiErrorResponse;

export type SkipResearchStatus422 = HTTPValidationError;

export type SkipResearchStatus503 = ApiErrorResponse;

export type SkipResearchOptions = {
  body?: never;
  path: SkipResearchPath;
  query?: never;
  headers?: never;
};

export type SkipResearchResponses = {
  '200': SkipResearchStatus200;
  '401': SkipResearchStatus401;
  '404': SkipResearchStatus404;
  '409': SkipResearchStatus409;
  '422': SkipResearchStatus422;
  '503': SkipResearchStatus503;
};

/**
 * @description Union of all possible responses
 */
export type SkipResearchResponse = SkipResearchStatus200;
