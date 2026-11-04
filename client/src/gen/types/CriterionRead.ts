// @ts-nocheck

export const criterionReadCriterionTypeEnum = {
  hard: 'hard',
  soft: 'soft',
} as const;

export type CriterionReadCriterionTypeEnumKey = (typeof criterionReadCriterionTypeEnum)[keyof typeof criterionReadCriterionTypeEnum];

export type CriterionRead = {
  criterion: string;
  criterion_type: CriterionReadCriterionTypeEnumKey;
  data_backing: string;
  result: string;
};
