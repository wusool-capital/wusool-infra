// @ts-nocheck

import type { ApiErrorResponse } from './ApiErrorResponse'
import type { BuyerSummary } from './BuyerSummary'
import type { HTTPValidationError } from './HTTPValidationError'

export type SearchBuyersQuery = {
  /**
   * @minLength 2
   * @maxLength 200
   * @type string
   */
  q: string;
};

export type SearchBuyersStatus200 = BuyerSummary[];

export type SearchBuyersStatus401 = ApiErrorResponse;

export type SearchBuyersStatus404 = ApiErrorResponse;

export type SearchBuyersStatus422 = HTTPValidationError;

export type SearchBuyersStatus503 = ApiErrorResponse;

export type SearchBuyersOptions = {
  body?: never;
  path?: never;
  query: SearchBuyersQuery;
  headers?: never;
};

export type SearchBuyersResponses = {
  '200': SearchBuyersStatus200;
  '401': SearchBuyersStatus401;
  '404': SearchBuyersStatus404;
  '422': SearchBuyersStatus422;
  '503': SearchBuyersStatus503;
};

/**
 * @description Union of all possible responses
 */
export type SearchBuyersResponse = SearchBuyersStatus200;
