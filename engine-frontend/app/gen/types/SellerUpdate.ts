// @ts-nocheck

export const sellerUpdateOpenToSelling = {
  Unknown: 'Unknown',
  Interested: 'Interested',
  'Warm intro': 'Warm intro',
} as const;

export type SellerUpdateOpenToSellingKey = (typeof sellerUpdateOpenToSelling)[keyof typeof sellerUpdateOpenToSelling];

export type SellerUpdate = {
  estEbitdaUsd?: number | (null | null);
  estRevenueUsd?: number | (null | null);
  openToSelling?: SellerUpdateOpenToSellingKey | (null | null);
  reEngageDate?: string | (null | null);
};
