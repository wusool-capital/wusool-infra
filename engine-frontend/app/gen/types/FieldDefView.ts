// @ts-nocheck

export const fieldDefViewGroupEnum = {
  role: 'role',
  company: 'company',
} as const;

export type FieldDefViewGroupEnumKey = (typeof fieldDefViewGroupEnum)[keyof typeof fieldDefViewGroupEnum];

export const fieldDefViewKindEnum = {
  text: 'text',
  multiline: 'multiline',
  select: 'select',
  multi_select: 'multi_select',
  currency: 'currency',
  percent: 'percent',
  number: 'number',
  date: 'date',
  bool: 'bool',
} as const;

export type FieldDefViewKindEnumKey = (typeof fieldDefViewKindEnum)[keyof typeof fieldDefViewKindEnum];

/**
 * @description A field the form draws by `kind`: a select or checklist from `options`, an amount, a date.
 * @type object
 */
export type FieldDefView = {
  clearable: boolean;
  group: FieldDefViewGroupEnumKey;
  key: string;
  kind: FieldDefViewKindEnumKey;
  label: string;
  options: string[];
};
