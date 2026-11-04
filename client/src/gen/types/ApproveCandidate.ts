// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { ApproveRequest } from './ApproveRequest'
import type { DecisionResponse } from './DecisionResponse'
import type { HTTPValidationError } from './HTTPValidationError'

export type ApproveCandidatePath = {
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

export type ApproveCandidateStatus200 = DecisionResponse;

export type ApproveCandidateStatus401 = ApiErrorResponse;

export type ApproveCandidateStatus404 = ApiErrorResponse;

export type ApproveCandidateStatus409 = ApiErrorResponse;

export type ApproveCandidateStatus422 = HTTPValidationError;

export type ApproveCandidateStatus502 = ApiErrorResponse;

export type ApproveCandidateStatus503 = ApiErrorResponse;

export type ApproveCandidateBody = ApproveRequest;

export type ApproveCandidateOptions = {
  body: ApproveCandidateBody;
  path: ApproveCandidatePath;
  query?: never;
  headers?: never;
};

export type ApproveCandidateResponses = {
  '200': ApproveCandidateStatus200;
  '401': ApproveCandidateStatus401;
  '404': ApproveCandidateStatus404;
  '409': ApproveCandidateStatus409;
  '422': ApproveCandidateStatus422;
  '502': ApproveCandidateStatus502;
  '503': ApproveCandidateStatus503;
};

/**
 * @description Union of all possible responses
 */
export type ApproveCandidateResponse = ApproveCandidateStatus200;
