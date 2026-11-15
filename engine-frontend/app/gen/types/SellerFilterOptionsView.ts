// @ts-nocheck

import type { FieldDefView } from './FieldDefView'

/**
 * @description `sector_choices` and `hq_countries` list everything Attio allows, for the add form.
 * @type object
 */
export type SellerFilterOptionsView = {
  fields: FieldDefView[];
  geographies: string[];
  hqCountries: string[];
  sectorChoices: string[];
  sectors: string[];
};
