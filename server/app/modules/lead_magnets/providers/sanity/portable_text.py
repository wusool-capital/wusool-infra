"""Sanity Portable Text, and pasted HTML, to the HTML Webflow's RichText stores.

Webflow stores whatever HTML the API sends, script tags included (checked
2026-10-07), so every body goes through `sanitize` before it leaves here. The
Studio's editor offers only what `_ALLOWED_TAGS` keeps.
"""

from html import escape
from typing import Annotated, Literal

import nh3
from pydantic import BaseModel, ConfigDict, Field

# Webflow fetches the image itself and rejects anything over 4MB.
_IMAGE_PARAMS = "?w=1600&fm=jpg"
_STYLES = {"normal": "p", "h2": "h2", "h3": "h3", "h4": "h4", "blockquote": "blockquote"}
_DECORATORS = {"strong", "em"}
_ALLOWED_TAGS = {
    *_STYLES.values(),
    *_DECORATORS,
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "a",
    "br",
    "code",
    "sup",
    "sub",
    "figure",
    "img",
    "figcaption",
}
_ALLOWED_ATTRIBUTES = {"a": {"href", "target"}, "img": {"src", "alt"}}


class _Span(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    marks: list[str] = []


class _MarkDef(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    key: str = Field(alias="_key")
    href: str | None = None


class TextBlock(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    type_: Literal["block"] = Field(alias="_type")
    style: str = "normal"
    children: list[_Span] = []
    mark_defs: list[_MarkDef] = Field(default=[], alias="markDefs")
    list_item: Literal["bullet", "number"] | None = Field(default=None, alias="listItem")
    level: int = 1


class ImageBlock(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    type_: Literal["image"] = Field(alias="_type")
    # Projected from `asset->url` in the GROQ query.
    url: str | None = None
    alt: str | None = None


Block = Annotated[TextBlock | ImageBlock, Field(discriminator="type_")]


def sanitize(html: str) -> str:
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
    )


def to_html(blocks: list[Block]) -> str:
    out: list[str] = []
    # Open list tags, innermost last; each still has an unclosed <li>.
    lists: list[str] = []
    for block in blocks:
        if isinstance(block, TextBlock) and block.list_item:
            tag = "ul" if block.list_item == "bullet" else "ol"
            while len(lists) > block.level or (len(lists) == block.level and lists[-1] != tag):
                out.append(f"</li></{lists.pop()}>")
            if len(lists) == block.level:
                out.append("</li><li>")
            while len(lists) < block.level:
                lists.append(tag)
                out.append(f"<{tag}><li>")
            out.append(_inline(block))
            continue
        while lists:
            out.append(f"</li></{lists.pop()}>")
        if isinstance(block, ImageBlock):
            if block.url:
                alt = escape(block.alt or "")
                out.append(
                    f'<figure><img src="{escape(block.url + _IMAGE_PARAMS)}" alt="{alt}"></figure>'
                )
        else:
            tag = _STYLES.get(block.style, "p")
            out.append(f"<{tag}>{_inline(block)}</{tag}>")
    while lists:
        out.append(f"</li></{lists.pop()}>")
    return sanitize("".join(out))


def _inline(block: TextBlock) -> str:
    links = {d.key: d.href for d in block.mark_defs if d.href}
    html = ""
    for span in block.children:
        text = escape(span.text).replace("\n", "<br>")
        for mark in span.marks:
            if mark in _DECORATORS:
                text = f"<{mark}>{text}</{mark}>"
            elif href := links.get(mark):
                text = f'<a href="{escape(href)}">{text}</a>'
        html += text
    return html
