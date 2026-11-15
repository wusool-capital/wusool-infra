// @ts-nocheck

export const personViewRoleEnum = {
  buyer: 'buyer',
  target: 'target',
} as const;

export type PersonViewRoleEnumKey = (typeof personViewRoleEnum)[keyof typeof personViewRoleEnum];

export type PersonView = {
  email?: string | (null | null);
  id: string;
  name: string;
  org: string;
  role: PersonViewRoleEnumKey;
  title?: string | (null | null);
};
