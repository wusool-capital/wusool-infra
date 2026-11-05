// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { DecisionResponse } from './DecisionResponse'
import type { SaveResearchRequest } from './SaveResearchRequest'

export type SaveResearchPath = {
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

export type SaveResearchStatus200 = DecisionResponse;

export type SaveResearchStatus401 = ApiErrorResponse;

export type SaveResearchStatus403 = ApiErrorResponse;

export type SaveResearchStatus404 = ApiErrorResponse;

export type SaveResearchStatus409 = ApiErrorResponse;

export type SaveResearchStatus422 = ApiErrorResponse;

export type SaveResearchStatus502 = ApiErrorResponse;

export type SaveResearchStatus503 = ApiErrorResponse;

export type SaveResearchBody = SaveResearchRequest;

export type SaveResearchOptions = {
  body: SaveResearchBody;
  path: SaveResearchPath;
  query?: never;
  headers?: never;
};

export type SaveResearchResponses = {
  '200': SaveResearchStatus200;
  '401': SaveResearchStatus401;
  '403': SaveResearchStatus403;
  '404': SaveResearchStatus404;
  '409': SaveResearchStatus409;
  '422': SaveResearchStatus422;
  '502': SaveResearchStatus502;
  '503': SaveResearchStatus503;
};

/**
 * @description Union of all possible responses
 */
export type SaveResearchResponse = SaveResearchStatus200;
