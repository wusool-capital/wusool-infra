import {defineField, defineType} from 'sanity'

// Exact Webflow option names; the sync resolves them to Webflow ids.
export const SILOS = [
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
        'The page URL: wusoolcapital.com/reports/<slug>. Must not reuse an existing report URL.',
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
      description: 'Optional. 2-3 sentences for the /reports card and search results.',
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
    defineField({name: 'silo', title: 'Primary silo', type: 'string', options: {list: SILOS}}),
    defineField({
      name: 'publishedAt',
      title: 'Published date',
      type: 'datetime',
      initialValue: () => new Date().toISOString(),
    }),
    defineField({
      name: 'featured',
      title: 'Pin to top of /reports',
      type: 'boolean',
      initialValue: false,
      description: 'Unpins whichever card is pinned now.',
    }),
    defineField({
      name: 'cta',
      title: 'End-of-page button',
      type: 'object',
      description:
        'Optional button below the report. Removing it here does not remove it from the site; clear it in Webflow too.',
      fields: [
        defineField({
          name: 'text',
          title: 'Button text',
          type: 'string',
          validation: (rule) => rule.max(80),
        }),
        defineField({
          name: 'url',
          title: 'Button link',
          type: 'url',
          description: 'A full URL, or a site path such as /sell.',
          // Existing article buttons use site paths like /sell and /valuation-tool.
          validation: (rule) => rule.uri({allowRelative: true, scheme: ['http', 'https']}),
        }),
      ],
      validation: (rule) =>
        rule.custom<{text?: string; url?: string}>((cta) =>
          Boolean(cta?.text) === Boolean(cta?.url)
            ? true
            : 'Fill in both the text and the link, or neither',
        ),
    }),
    // Written by the toolkit server after each publish: the report as a browser draws it.
    defineField({name: 'renderedHtml', type: 'text', hidden: true, readOnly: true}),
    defineField({name: 'renderedPreviewEnd', type: 'number', hidden: true, readOnly: true}),
    defineField({name: 'renderedFrom', type: 'string', hidden: true, readOnly: true}),
  ],
})
