import {defineField, defineType} from 'sanity'

import {SILOS} from './report'
import {bodyFormat, isHtml, isRich, richText} from './richText'

// Exact Webflow names; the sync resolves them to Webflow ids. "Report" belongs to /reports.
const CONTENT_TYPES = ['Article', 'Playbook', 'Case Study', 'Press']
const AUTHORS = ['Jules Chasles', 'Hugo Cugnet', 'Ramzy Osman', 'Maria Najjar']

// One rich-text field and its pasted-HTML twin; `bodyFormat` shows one of the pair.
const richOrHtml = (name: string, title: string, required: boolean) => [
  defineField({
    name,
    title,
    type: 'array',
    group: 'content',
    of: richText,
    hidden: isHtml,
    validation: (rule) =>
      rule.custom((value, context) =>
        required && isRich({document: context.document}) && !value?.length
          ? 'Required'
          : true,
      ),
  }),
  defineField({
    name: `${name}Html`,
    title: `${title} (HTML)`,
    type: 'text',
    group: 'content',
    rows: 16,
    description: 'Scripts, styles and anything Webflow rich text cannot show are removed on publish.',
    hidden: isRich,
    validation: (rule) =>
      rule.custom((value, context) =>
        required && isHtml({document: context.document}) && !value?.trim()
          ? 'Required'
          : true,
      ),
  }),
]

export const insights = defineType({
  name: 'insights',
  title: 'Insights article',
  type: 'document',
  groups: [
    {name: 'content', title: 'Content', default: true},
    {name: 'seo', title: 'SEO'},
    {name: 'publishing', title: 'Publishing'},
  ],
  fields: [
    defineField({
      name: 'title',
      group: 'content',
      type: 'string',
      validation: (rule) => rule.required().max(256),
    }),
    defineField({
      name: 'slug',
      group: 'content',
      type: 'slug',
      description:
        'The page URL: wusoolcapital.com/insights/<slug>. If a hand-written Webflow article already uses this slug, publishing is skipped.',
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
      name: 'contentType',
      group: 'content',
      title: 'Content type',
      type: 'string',
      options: {list: CONTENT_TYPES},
      initialValue: 'Article',
      validation: (rule) => rule.required(),
    }),
    defineField({
      name: 'excerpt',
      group: 'content',
      type: 'text',
      rows: 3,
      description: '2-3 sentences for the /insights card and search results.',
      validation: (rule) => rule.required(),
    }),
    bodyFormat('rich', 'Applies to the body, key takeaways and FAQ.'),
    ...richOrHtml('body', 'Body', true),
    ...richOrHtml('keyTakeaways', 'Key takeaways', false),
    ...richOrHtml('faq', 'FAQ', false),
    defineField({name: 'cover', group: 'content', title: 'Cover image', type: 'image'}),
    defineField({name: 'author', group: 'content', type: 'string', options: {list: AUTHORS}}),
    defineField({name: 'silo', group: 'publishing', title: 'Primary silo', type: 'string', options: {list: SILOS}}),
    defineField({
      name: 'publishedAt',
      group: 'publishing',
      title: 'Published date',
      type: 'datetime',
      initialValue: () => new Date().toISOString(),
    }),
    defineField({
      name: 'featured',
      group: 'publishing',
      title: 'Pin to top of /insights',
      type: 'boolean',
      initialValue: false,
      description:
        'Unpins whichever article is pinned now, hand-written ones included. With nothing pinned, the newest article shows there instead.',
    }),
    defineField({
      name: 'h1',
      group: 'seo',
      title: 'H1',
      type: 'string',
      description: 'Keyword-targeted page heading. Leave blank to use the title.',
    }),
    defineField({
      name: 'seoTitle',
      group: 'seo',
      title: 'SEO title',
      type: 'string',
      description: 'Max 60 characters. Leave blank to use the title.',
      validation: (rule) => rule.max(60).warning(),
    }),
    defineField({
      name: 'seoDescription',
      group: 'seo',
      title: 'SEO description',
      type: 'text',
      rows: 2,
      description: 'Max 155 characters. Leave blank to use the excerpt.',
      validation: (rule) => rule.max(155).warning(),
    }),
    defineField({
      name: 'ogTitle',
      group: 'seo',
      title: 'Share title',
      type: 'string',
      description: 'Shown when the page is shared on WhatsApp or LinkedIn. Leave blank to use the title.',
    }),
    defineField({name: 'targetKeyword', group: 'seo', title: 'Target keyword', type: 'string'}),
    defineField({
      name: 'cta',
      group: 'content',
      title: 'End-of-page button',
      type: 'object',
      description:
        'Optional button below the article. Removing it here does not remove it from the site; clear it in Webflow too.',
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
  ],
})
