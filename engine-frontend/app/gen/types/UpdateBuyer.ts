// @ts-nocheck

import type { BuyerRoleView } from './BuyerRoleView'
import type { BuyerUpdate } from './BuyerUpdate'
import type { ProblemDetail } from './ProblemDetail'

export type UpdateBuyerPath = {
  role_id: string;
};

export type UpdateBuyerHeaders = {
  'if-match'?: string | (null | null);
};

export type UpdateBuyerStatus200 = BuyerRoleView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type UpdateBuyerStatus503 = ProblemDetail;

/**
 * @description Only the fields sent change. A value can be changed but not emptied; a null is refused.
 * @type object
 */
export type UpdateBuyerBody = BuyerUpdate;

export type UpdateBuyerOptions = {
  body: UpdateBuyerBody;
  path: UpdateBuyerPath;
  query?: never;
  headers?: UpdateBuyerHeaders;
};

export type UpdateBuyerResponses = {
  '200': UpdateBuyerStatus200;
  '400': UpdateBuyerStatus400;
  '401': UpdateBuyerStatus401;
  '403': UpdateBuyerStatus403;
  '404': UpdateBuyerStatus404;
  '409': UpdateBuyerStatus409;
  '412': UpdateBuyerStatus412;
  '422': UpdateBuyerStatus422;
  '428': UpdateBuyerStatus428;
  '502': UpdateBuyerStatus502;
  '503': UpdateBuyerStatus503;
};

/**
 * @description Union of all possible responses
 */
export type UpdateBuyerResponse = UpdateBuyerStatus200;
