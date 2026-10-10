import {defineConfig} from 'sanity'
import {structureTool} from 'sanity/structure'

import {insights} from './schemaTypes/insights'
import {report} from './schemaTypes/report'

export default defineConfig({
  name: 'default',
  title: 'Wusool Reports & Insights',
  projectId: process.env.SANITY_STUDIO_PROJECT_ID ?? 'itidwo8t',
  dataset: process.env.SANITY_STUDIO_DATASET ?? 'production',
  plugins: [structureTool()],
  schema: {types: [report, insights]},
})
