// @ts-nocheck

import type { ProblemDetail } from './ProblemDetail'
import type { SellersUniverseView } from './SellersUniverseView'

export type GetSellersUniverseQuery = {
  /**
   * @default ''
   * @type string | undefined
   */
  q?: string;
  cursor?: string | (null | null);
  /**
   * @minimum 1
   * @maximum 100
   * @default 100
   * @type integer | undefined
   */
  limit?: number;
  sector?: string | (null | null);
  geography?: string | (null | null);
  revenue?: string | (null | null);
  ebitda?: string | (null | null);
  openToSelling?: string | (null | null);
};

export type GetSellersUniverseStatus200 = SellersUniverseView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellersUniverseStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellersUniverseStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellersUniverseStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellersUniverseStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellersUniverseStatus503 = ProblemDetail;

export type GetSellersUniverseOptions = {
  body?: never;
  path?: never;
  query?: GetSellersUniverseQuery;
  headers?: never;
};

export type GetSellersUniverseResponses = {
  '200': GetSellersUniverseStatus200;
  '400': GetSellersUniverseStatus400;
  '401': GetSellersUniverseStatus401;
  '403': GetSellersUniverseStatus403;
  '422': GetSellersUniverseStatus422;
  '503': GetSellersUniverseStatus503;
};

/**
 * @description Union of all possible responses
 */
export type GetSellersUniverseResponse = GetSellersUniverseStatus200;
