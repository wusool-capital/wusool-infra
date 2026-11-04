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

export const exportMatchRunFieldsEnum = {
  rank: 'rank',
  origin: 'origin',
  seller: 'seller',
  seller_attio_id: 'seller_attio_id',
  match_score: 'match_score',
  data_confidence: 'data_confidence',
  status: 'status',
  why_it_matches: 'why_it_matches',
  why_chosen_over_alternatives: 'why_chosen_over_alternatives',
  recommended_pitch: 'recommended_pitch',
  risks_and_gaps: 'risks_and_gaps',
  source_url: 'source_url',
  research_saved: 'research_saved',
} as const;

export type ExportMatchRunFieldsEnumKey = (typeof exportMatchRunFieldsEnum)[keyof typeof exportMatchRunFieldsEnum];

export type ExportMatchRunQuery = {
  fields?: ExportMatchRunFieldsEnumKey[] | null;
};

export type ExportMatchRunStatus200 = Blob;

export type ExportMatchRunStatus401 = ApiErrorResponse;

export type ExportMatchRunStatus404 = ApiErrorResponse;

export type ExportMatchRunStatus422 = HTTPValidationError;

export type ExportMatchRunStatus503 = ApiErrorResponse;

export type ExportMatchRunOptions = {
  body?: never;
  path: ExportMatchRunPath;
  query?: ExportMatchRunQuery;
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
