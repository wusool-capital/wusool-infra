// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { DecisionResponse } from './DecisionResponse'
import type { HTTPValidationError } from './HTTPValidationError'

export type RejectCandidatePath = {
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

export type RejectCandidateStatus200 = DecisionResponse;

export type RejectCandidateStatus401 = ApiErrorResponse;

export type RejectCandidateStatus404 = ApiErrorResponse;

export type RejectCandidateStatus409 = ApiErrorResponse;

export type RejectCandidateStatus422 = HTTPValidationError;

export type RejectCandidateStatus503 = ApiErrorResponse;

export type RejectCandidateOptions = {
  body?: never;
  path: RejectCandidatePath;
  query?: never;
  headers?: never;
};

export type RejectCandidateResponses = {
  '200': RejectCandidateStatus200;
  '401': RejectCandidateStatus401;
  '404': RejectCandidateStatus404;
  '409': RejectCandidateStatus409;
  '422': RejectCandidateStatus422;
  '503': RejectCandidateStatus503;
};

/**
 * @description Union of all possible responses
 */
export type RejectCandidateResponse = RejectCandidateStatus200;
