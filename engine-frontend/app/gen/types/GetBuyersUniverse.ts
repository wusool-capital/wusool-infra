// @ts-nocheck

import type { BuyersUniverseView } from './BuyersUniverseView'
import type { ProblemDetail } from './ProblemDetail'

export type GetBuyersUniverseQuery = {
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
  checkSize?: string | (null | null);
  minEbitda?: string | (null | null);
};

export type GetBuyersUniverseStatus200 = BuyersUniverseView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyersUniverseStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyersUniverseStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyersUniverseStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyersUniverseStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyersUniverseStatus503 = ProblemDetail;

export type GetBuyersUniverseOptions = {
  body?: never;
  path?: never;
  query?: GetBuyersUniverseQuery;
  headers?: never;
};

export type GetBuyersUniverseResponses = {
  '200': GetBuyersUniverseStatus200;
  '400': GetBuyersUniverseStatus400;
  '401': GetBuyersUniverseStatus401;
  '403': GetBuyersUniverseStatus403;
  '422': GetBuyersUniverseStatus422;
  '503': GetBuyersUniverseStatus503;
};

/**
 * @description Union of all possible responses
 */
export type GetBuyersUniverseResponse = GetBuyersUniverseStatus200;
