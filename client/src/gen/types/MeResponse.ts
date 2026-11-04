// @ts-nocheck

export const meResponseViaEnum = {
  slack: 'slack',
  key: 'key',
} as const;

export type MeResponseViaEnumKey = (typeof meResponseViaEnum)[keyof typeof meResponseViaEnum];

export type MeResponse = {
  name: string | null;
  slack_user_id: string | null;
  via: MeResponseViaEnumKey;
};
