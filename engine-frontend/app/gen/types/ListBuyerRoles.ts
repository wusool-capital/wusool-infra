// @ts-nocheck

import type { BuyerRolePage } from './BuyerRolePage'
import type { ProblemDetail } from './ProblemDetail'

export type ListBuyerRolesQuery = {
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

/**
 * @description `matched` counts rows under the filters and search; `total` counts every live buyer.
 *
 * `matched`, `total` and `options` come with the first page; later pages hold rows only.
 * @type object
 */
export type ListBuyerRolesStatus200 = BuyerRolePage;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListBuyerRolesStatus503 = ProblemDetail;

export type ListBuyerRolesOptions = {
  body?: never;
  path?: never;
  query?: ListBuyerRolesQuery;
  headers?: never;
};

export type ListBuyerRolesResponses = {
  '200': ListBuyerRolesStatus200;
  '400': ListBuyerRolesStatus400;
  '401': ListBuyerRolesStatus401;
  '403': ListBuyerRolesStatus403;
  '404': ListBuyerRolesStatus404;
  '409': ListBuyerRolesStatus409;
  '412': ListBuyerRolesStatus412;
  '422': ListBuyerRolesStatus422;
  '428': ListBuyerRolesStatus428;
  '502': ListBuyerRolesStatus502;
  '503': ListBuyerRolesStatus503;
};

/**
 * @description Union of all possible responses
 */
export type ListBuyerRolesResponse = ListBuyerRolesStatus200;
