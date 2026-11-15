// @ts-nocheck

import type { ProblemDetail } from './ProblemDetail'
import type { SellerRolePage } from './SellerRolePage'

export type ListSellerRolesQuery = {
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

/**
 * @description Counts and options come with the first page, as for buyers.
 * @type object
 */
export type ListSellerRolesStatus200 = SellerRolePage;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ListSellerRolesStatus503 = ProblemDetail;

export type ListSellerRolesOptions = {
  body?: never;
  path?: never;
  query?: ListSellerRolesQuery;
  headers?: never;
};

export type ListSellerRolesResponses = {
  '200': ListSellerRolesStatus200;
  '400': ListSellerRolesStatus400;
  '401': ListSellerRolesStatus401;
  '403': ListSellerRolesStatus403;
  '404': ListSellerRolesStatus404;
  '409': ListSellerRolesStatus409;
  '412': ListSellerRolesStatus412;
  '422': ListSellerRolesStatus422;
  '428': ListSellerRolesStatus428;
  '502': ListSellerRolesStatus502;
  '503': ListSellerRolesStatus503;
};

/**
 * @description Union of all possible responses
 */
export type ListSellerRolesResponse = ListSellerRolesStatus200;
