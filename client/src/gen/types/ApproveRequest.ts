// @ts-nocheck

export const approveRequestResolution = {
  promote_existing: 'promote_existing',
  create_new: 'create_new',
} as const;

export type ApproveRequestResolutionKey = (typeof approveRequestResolution)[keyof typeof approveRequestResolution];

export type ApproveRequest = {
  existing_deal_id?: string | null;
  resolution?: ApproveRequestResolutionKey | null;
};
