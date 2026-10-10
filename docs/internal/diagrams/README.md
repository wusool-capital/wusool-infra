# GitBook diagrams

Editable sources for the diagrams in `gitbook/`. Each `<name>.html` here is
published as `gitbook/.gitbook/assets/<name>.svg`.

They follow [diagram-design](https://github.com/cathrynlavery/diagram-design)
with the default skin and system fonts. GitBook shows images through an
`<img>` tag, which can't load web fonts.

To update a diagram, edit its HTML, then export and copy the SVG:

```bash
python3 <diagram-design>/skills/diagram-design/scripts/export_svg.py <name>.html --system-fonts
cp <name>.svg ../../../gitbook/.gitbook/assets/
```
