import {defineField, defineType} from 'sanity'

import {bodyFormat, isHtml, isRich, richText} from './richText'

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
    // Missing on reports made before the toggle, which are all pasted HTML.
    bodyFormat(
      'html',
      'Pasted HTML keeps an exported design and its pages; readers see page one, then the form. A rich text report shows its first quarter.',
    ),
    defineField({
      name: 'body',
      title: 'Report',
      type: 'array',
      of: richText,
      hidden: isHtml,
      validation: (rule) =>
        rule.custom((value, context) =>
          isRich({document: context.document}) && !value?.length ? 'Required' : true,
        ),
    }),
    defineField({
      name: 'html',
      title: 'Report HTML',
      type: 'text',
      rows: 20,
      description: 'Paste the full report HTML. Readers see the first page, then the form.',
      hidden: isRich,
      validation: (rule) =>
        rule.custom((value, context) =>
          !isRich({document: context.document}) && !value?.trim() ? 'Required' : true,
        ),
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
