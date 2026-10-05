import {defineConfig} from 'sanity'
import {structureTool} from 'sanity/structure'

import {report} from './schemaTypes/report'

export default defineConfig({
  name: 'default',
  title: 'Wusool Reports',
  projectId: process.env.SANITY_STUDIO_PROJECT_ID ?? '',
  dataset: process.env.SANITY_STUDIO_DATASET ?? 'production',
  plugins: [structureTool()],
  schema: {types: [report]},
})
