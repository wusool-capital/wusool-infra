// @ts-nocheck

import type { DetailInput } from './DetailInput'

export const sellerUpdateOpenToSelling = {
  Unknown: 'Unknown',
  Interested: 'Interested',
  'Warm intro': 'Warm intro',
} as const;

export type SellerUpdateOpenToSellingKey = (typeof sellerUpdateOpenToSelling)[keyof typeof sellerUpdateOpenToSelling];

export type SellerUpdate = {
  details?: DetailInput[];
  estEbitdaUsd?: number | (null | null);
  estRevenueUsd?: number | (null | null);
  openToSelling?: SellerUpdateOpenToSellingKey | (null | null);
  reEngageDate?: string | (null | null);
};
