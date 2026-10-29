import {defineArrayMember, defineField, type SanityDocument} from 'sanity'

export type Context = {document?: SanityDocument}
// Unset reads as pasted HTML: reports made before the toggle have none. New documents always set it.
export const isRich = ({document}: Context) => document?.bodyFormat === 'rich'
export const isHtml = ({document}: Context) => !isRich({document})

// Only what the server's sanitizer keeps and Webflow's rich text renders.
export const richText = [
  defineArrayMember({
    type: 'block',
    styles: [
      {title: 'Normal', value: 'normal'},
      {title: 'Heading 2', value: 'h2'},
      {title: 'Heading 3', value: 'h3'},
      {title: 'Heading 4', value: 'h4'},
      {title: 'Heading 5', value: 'h5'},
      {title: 'Heading 6', value: 'h6'},
      {title: 'Quote', value: 'blockquote'},
    ],
    lists: [
      {title: 'Bullet', value: 'bullet'},
      {title: 'Numbered', value: 'number'},
    ],
    marks: {
      decorators: [
        {title: 'Bold', value: 'strong'},
        {title: 'Italic', value: 'em'},
        {title: 'Underline', value: 'underline'},
        {title: 'Strike', value: 'strike-through'},
        {title: 'Code', value: 'code'},
        {title: 'Superscript', value: 'sup'},
        {title: 'Subscript', value: 'sub'},
      ],
      annotations: [
        defineArrayMember({
          name: 'link',
          type: 'object',
          title: 'Link',
          fields: [
            defineField({
              name: 'href',
              type: 'url',
              description: 'A full URL, or a site path such as /sell.',
              validation: (rule) =>
                rule.required().uri({allowRelative: true, scheme: ['http', 'https', 'mailto']}),
            }),
            defineField({name: 'blank', title: 'Open in new tab', type: 'boolean'}),
          ],
        }),
      ],
    },
  }),
  defineArrayMember({
    type: 'image',
    fields: [defineField({name: 'alt', title: 'Alt text', type: 'string'})],
  }),
]

// A chart from the article's HTML file: a still image in the page, live once the reader scrolls to it.
export const exhibit = defineArrayMember({
  name: 'exhibit',
  type: 'object',
  title: 'Chart from the HTML file',
  fields: [
    defineField({
      name: 'exhibitId',
      title: 'Chart id',
      type: 'string',
      description: 'Section id and figure number in the HTML file, such as beat-3#0.',
      validation: (rule) => rule.required().regex(/^[A-Za-z0-9_-]+#\d+$/, 'Like beat-3#0'),
    }),
    defineField({name: 'alt', title: 'Alt text', type: 'string', validation: (rule) => rule.required()}),
    defineField({
      name: 'live',
      title: 'Interactive',
      type: 'boolean',
      initialValue: true,
      description: 'Off keeps the still image, for charts that do nothing when clicked.',
    }),
  ],
  preview: {select: {title: 'exhibitId', subtitle: 'alt'}},
})

// Which of a document's rich-text / pasted-HTML pairs is shown and published.
export const bodyFormat = (initial: 'rich' | 'html', description: string) =>
  defineField({
    name: 'bodyFormat',
    title: 'Write with',
    group: 'content',
    type: 'string',
    options: {
      list: [
        {title: 'Rich text editor', value: 'rich'},
        {title: 'Pasted HTML', value: 'html'},
      ],
      layout: 'radio',
      direction: 'horizontal',
    },
    initialValue: initial,
    description,
  })
