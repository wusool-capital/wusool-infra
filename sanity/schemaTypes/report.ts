import {defineField, defineType} from 'sanity'

// Exact Webflow names: the sync resolves them to Webflow ids by name.
// Team collection and the Insights "Primary Silo" options, read 2026-10-05.
const AUTHORS = ['Jules Chasles', 'Hugo Cugnet', 'Ramzy Osman', 'Maria Najjar']
const SILOS = [
  'Sell Your Business',
  'Business Valuation',
  'Exit Strategy',
  'Buy a Business',
  'GCC M&A Market',
  'General',
  'Entrepreneurship Through Acquisition (ETA) GCC',
]

export const report = defineType({
  name: 'report',
  title: 'Report',
  type: 'document',
  fields: [
    defineField({
      name: 'title',
      type: 'string',
      validation: (rule) => rule.required().max(256),
    }),
    defineField({
      name: 'slug',
      type: 'slug',
      description:
        'The page URL: wusoolcapital.com/insights/<slug>. Must not reuse an existing article URL.',
      options: {source: 'title', maxLength: 96},
      validation: (rule) =>
        rule
          .required()
          .custom((slug) =>
            /^[a-z0-9-]+$/.test(slug?.current ?? '')
              ? true
              : 'Lowercase letters, numbers and hyphens only',
          ),
    }),
    defineField({
      name: 'excerpt',
      type: 'text',
      rows: 3,
      description: '2-3 sentences for the /insights card and search results.',
      validation: (rule) => rule.required(),
    }),
    defineField({
      name: 'html',
      title: 'Report HTML',
      type: 'text',
      rows: 20,
      description: 'Paste the full report HTML. Readers see the first 25%, then the form.',
      validation: (rule) => rule.required(),
    }),
    defineField({name: 'cover', title: 'Cover image', type: 'image'}),
    defineField({name: 'author', type: 'string', options: {list: AUTHORS}}),
    defineField({name: 'silo', title: 'Primary silo', type: 'string', options: {list: SILOS}}),
    defineField({
      name: 'publishedAt',
      title: 'Published date',
      type: 'datetime',
      initialValue: () => new Date().toISOString(),
    }),
    defineField({
      name: 'featured',
      title: 'Pin to top of /insights',
      type: 'boolean',
      initialValue: false,
      description: 'Unpins whichever card is pinned now.',
    }),
    // Written by the toolkit server after each publish: the report as a browser draws it.
    defineField({name: 'renderedHtml', type: 'text', hidden: true, readOnly: true}),
    defineField({name: 'renderedFrom', type: 'string', hidden: true, readOnly: true}),
  ],
})
