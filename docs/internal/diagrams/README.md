# GitBook diagrams

Editable sources for the diagrams in `gitbook/`. Each `<name>.html` here is
published as `gitbook/.gitbook/assets/<name>.svg`.

They follow [diagram-design](https://github.com/cathrynlavery/diagram-design)
with a Wusool skin taken from wusoolcapital.com: Gold White `#f7f5f0` paper,
Midnight Blue `#000523` ink, and Gulf Blue `#c6e1ee` for the focal node. The
accent `#336a85` is Gulf Blue darkened to pass contrast as a line. Labels use
Inter where installed and the system sans otherwise, because GitBook shows
images through an `<img>` tag, which can't load web fonts.

To update a diagram, edit its HTML, then export and copy the SVG:

```bash
python3 <diagram-design>/skills/diagram-design/scripts/export_svg.py <name>.html --system-fonts
cp <name>.svg ../../../gitbook/.gitbook/assets/
```
