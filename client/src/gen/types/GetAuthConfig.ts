// @ts-nocheck

import type { AuthConfigResponse } from './AuthConfigResponse'

/**
 * @description Which sign-in methods the page should offer.
 * @type object
 */
export type GetAuthConfigStatus200 = AuthConfigResponse;

export type GetAuthConfigOptions = {
  body?: never;
  path?: never;
  query?: never;
  headers?: never;
};

export type GetAuthConfigResponses = {
  '200': GetAuthConfigStatus200;
};

/**
 * @description Union of all possible responses
 */
export type GetAuthConfigResponse = GetAuthConfigStatus200;
