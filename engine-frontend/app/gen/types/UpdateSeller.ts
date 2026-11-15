// @ts-nocheck

import type { ProblemDetail } from './ProblemDetail'
import type { SellerRoleView } from './SellerRoleView'
import type { SellerUpdate } from './SellerUpdate'

export type UpdateSellerPath = {
  role_id: string;
};

export type UpdateSellerHeaders = {
  'if-match'?: string | (null | null);
};

export type UpdateSellerStatus200 = SellerRoleView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateSellerStatus503 = ProblemDetail;

export type UpdateSellerBody = SellerUpdate;

export type UpdateSellerOptions = {
  body: UpdateSellerBody;
  path: UpdateSellerPath;
  query?: never;
  headers?: UpdateSellerHeaders;
};

export type UpdateSellerResponses = {
  '200': UpdateSellerStatus200;
  '400': UpdateSellerStatus400;
  '401': UpdateSellerStatus401;
  '403': UpdateSellerStatus403;
  '404': UpdateSellerStatus404;
  '409': UpdateSellerStatus409;
  '412': UpdateSellerStatus412;
  '422': UpdateSellerStatus422;
  '428': UpdateSellerStatus428;
  '502': UpdateSellerStatus502;
  '503': UpdateSellerStatus503;
};

/**
 * @description Union of all possible responses
 */
export type UpdateSellerResponse = UpdateSellerStatus200;
