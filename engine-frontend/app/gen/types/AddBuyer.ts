// @ts-nocheck

import type { BuyerCreate } from './BuyerCreate'
import type { BuyerRoleView } from './BuyerRoleView'
import type { ProblemDetail } from './ProblemDetail'

export type AddBuyerStatus201 = BuyerRoleView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type AddBuyerStatus503 = ProblemDetail;

export type AddBuyerBody = BuyerCreate;

export type AddBuyerOptions = {
  body: AddBuyerBody;
  path?: never;
  query?: never;
  headers?: never;
};

export type AddBuyerResponses = {
  '201': AddBuyerStatus201;
  '400': AddBuyerStatus400;
  '401': AddBuyerStatus401;
  '403': AddBuyerStatus403;
  '404': AddBuyerStatus404;
  '409': AddBuyerStatus409;
  '412': AddBuyerStatus412;
  '422': AddBuyerStatus422;
  '428': AddBuyerStatus428;
  '502': AddBuyerStatus502;
  '503': AddBuyerStatus503;
};

/**
 * @description Union of all possible responses
 */
export type AddBuyerResponse = AddBuyerStatus201;
