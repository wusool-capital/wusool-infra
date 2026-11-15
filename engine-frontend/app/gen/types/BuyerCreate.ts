// @ts-nocheck

export type BuyerCreate = {
  checkSizeMaxUsd?: number | (null | null);
  checkSizeMinUsd?: number | (null | null);
  ebitdaFloorUsd?: number | (null | null);
  geographies?: string[] | (null | null);
  hq?: string | (null | null);
  /**
   * @minLength 1
   * @type string
   */
  name: string;
  notes?: string | (null | null);
  /**
   * @minLength 1
   * @type string
   */
  sector: string;
  status?: string | (null | null);
  /**
   * @minLength 1
   * @type string
   */
  website: string;
};
