// @ts-nocheck

import type { ProblemDetail } from './ProblemDetail'
import type { SellerCreate } from './SellerCreate'
import type { SellerRoleView } from './SellerRoleView'

export type AddSellerStatus201 = SellerRoleView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddSellerStatus503 = ProblemDetail;

export type AddSellerBody = SellerCreate;

export type AddSellerOptions = {
  body: AddSellerBody;
  path?: never;
  query?: never;
  headers?: never;
};

export type AddSellerResponses = {
  '201': AddSellerStatus201;
  '400': AddSellerStatus400;
  '401': AddSellerStatus401;
  '403': AddSellerStatus403;
  '404': AddSellerStatus404;
  '409': AddSellerStatus409;
  '412': AddSellerStatus412;
  '422': AddSellerStatus422;
  '428': AddSellerStatus428;
  '502': AddSellerStatus502;
  '503': AddSellerStatus503;
};

/**
 * @description Union of all possible responses
 */
export type AddSellerResponse = AddSellerStatus201;
