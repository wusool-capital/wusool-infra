// @ts-nocheck

import type { MeView } from './MeView'
import type { ProblemDetail } from './ProblemDetail'

export type GetCurrentUserStatus200 = MeView;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus400 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus401 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus403 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus404 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus409 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus412 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus422 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus428 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus502 = ProblemDetail;

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type GetCurrentUserStatus503 = ProblemDetail;

export type GetCurrentUserOptions = {
  body?: never;
  path?: never;
  query?: never;
  headers?: never;
};

export type GetCurrentUserResponses = {
  '200': GetCurrentUserStatus200;
  '400': GetCurrentUserStatus400;
  '401': GetCurrentUserStatus401;
  '403': GetCurrentUserStatus403;
  '404': GetCurrentUserStatus404;
  '409': GetCurrentUserStatus409;
  '412': GetCurrentUserStatus412;
  '422': GetCurrentUserStatus422;
  '428': GetCurrentUserStatus428;
  '502': GetCurrentUserStatus502;
  '503': GetCurrentUserStatus503;
};

/**
 * @description Union of all possible responses
 */
export type GetCurrentUserResponse = GetCurrentUserStatus200;
