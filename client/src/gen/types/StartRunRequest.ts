// @ts-nocheck

export type StartRunRequest = {
  advisor_context?: string | null;
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  buyer_role_id: string;
  request_id?: string | null;
};
