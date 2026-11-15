// @ts-nocheck

import type { BuyerRoleView } from './BuyerRoleView'
import type { ProblemDetail } from './ProblemDetail'

export type GetBuyerRolePath = {
  role_id: string;
};

export type GetBuyerRoleStatus200 = BuyerRoleView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetBuyerRoleStatus503 = ProblemDetail;

export type GetBuyerRoleOptions = {
  body?: never;
  path: GetBuyerRolePath;
  query?: never;
  headers?: never;
};

export type GetBuyerRoleResponses = {
  '200': GetBuyerRoleStatus200;
  '400': GetBuyerRoleStatus400;
  '401': GetBuyerRoleStatus401;
  '403': GetBuyerRoleStatus403;
  '404': GetBuyerRoleStatus404;
  '409': GetBuyerRoleStatus409;
  '412': GetBuyerRoleStatus412;
  '422': GetBuyerRoleStatus422;
  '428': GetBuyerRoleStatus428;
  '502': GetBuyerRoleStatus502;
  '503': GetBuyerRoleStatus503;
};

/**
 * @description Union of all possible responses
 */
export type GetBuyerRoleResponse = GetBuyerRoleStatus200;
