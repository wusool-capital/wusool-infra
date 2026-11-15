// @ts-nocheck

export const sellerCreateOpenToSelling = {
  Unknown: 'Unknown',
  Interested: 'Interested',
  'Warm intro': 'Warm intro',
} as const;

export type SellerCreateOpenToSellingKey = (typeof sellerCreateOpenToSelling)[keyof typeof sellerCreateOpenToSelling];

export type SellerCreate = {
  estEbitdaUsd?: number | (null | null);
  estRevenueUsd?: number | (null | null);
  hq?: string | (null | null);
  /**
   * @minLength 1
   * @type string
   */
  name: string;
  openToSelling?: SellerCreateOpenToSellingKey | (null | null);
  reEngageDate?: string | (null | null);
  /**
   * @minLength 1
   * @type string
   */
  sector: string;
  /**
   * @minLength 1
   * @type string
   */
  website: string;
};
