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

// Which of a document's rich-text / pasted-HTML pairs is shown and published.
export const bodyFormat = (initial: 'rich' | 'html', description: string) =>
  defineField({
    name: 'bodyFormat',
    title: 'Write with',
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
