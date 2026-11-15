// @ts-nocheck

import type { ProblemDetail } from './ProblemDetail'
import type { SellerRoleView } from './SellerRoleView'

export type GetSellerRolePath = {
  role_id: string;
};

export type GetSellerRoleStatus200 = SellerRoleView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetSellerRoleStatus503 = ProblemDetail;

export type GetSellerRoleOptions = {
  body?: never;
  path: GetSellerRolePath;
  query?: never;
  headers?: never;
};

export type GetSellerRoleResponses = {
  '200': GetSellerRoleStatus200;
  '400': GetSellerRoleStatus400;
  '401': GetSellerRoleStatus401;
  '403': GetSellerRoleStatus403;
  '404': GetSellerRoleStatus404;
  '409': GetSellerRoleStatus409;
  '412': GetSellerRoleStatus412;
  '422': GetSellerRoleStatus422;
  '428': GetSellerRoleStatus428;
  '502': GetSellerRoleStatus502;
  '503': GetSellerRoleStatus503;
};

/**
 * @description Union of all possible responses
 */
export type GetSellerRoleResponse = GetSellerRoleStatus200;
