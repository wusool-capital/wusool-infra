// @ts-nocheck

import type { ExistingDealRead } from './ExistingDealRead'

export const apiErrorCodeEnum = {
  unauthorized: 'unauthorized',
  web_disabled: 'web_disabled',
  not_found: 'not_found',
  already_reviewed: 'already_reviewed',
  existing_deals: 'existing_deals',
  partial_write: 'partial_write',
  run_not_ready: 'run_not_ready',
} as const;

export type ApiErrorCodeEnumKey = (typeof apiErrorCodeEnum)[keyof typeof apiErrorCodeEnum];

export type ApiError = {
  code: ApiErrorCodeEnumKey;
  /**
   * @default []
   * @type array
   */
  existing_deals: ExistingDealRead[];
  message: string;
};
