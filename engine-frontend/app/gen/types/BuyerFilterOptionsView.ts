// @ts-nocheck

import type { FieldDefView } from './FieldDefView'

/**
 * @description `regions` and `countries` list everything Attio allows, for the edit form.
 * @type object
 */
export type BuyerFilterOptionsView = {
  countries: string[];
  fields: FieldDefView[];
  geographies: string[];
  hqCountries: string[];
  regions: string[];
  sectorChoices: string[];
  sectors: string[];
  statuses: string[];
};
