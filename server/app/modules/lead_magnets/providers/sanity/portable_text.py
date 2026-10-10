"""Sanity Portable Text, and pasted HTML, to the HTML Webflow's RichText stores,
and a rich text report to a page the report pipeline can render, gate and print.

Webflow stores whatever HTML the API sends, script tags included (checked
2026-10-07), so every body goes through `sanitize` before it leaves here. The
Studio's editor offers only what `_ALLOWED_TAGS` keeps.
"""

import re
from html import escape
from typing import Annotated, Literal

import nh3
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.providers.sanity.images import resized

_STYLES = {
    "normal": "p",
    "h2": "h2",
    "h3": "h3",
    "h4": "h4",
    "h5": "h5",
    "h6": "h6",
    "blockquote": "blockquote",
}
# Sanity's built-in decorator names to the tag each one writes.
_DECORATORS = {
    "strong": "strong",
    "em": "em",
    "underline": "u",
    "strike-through": "s",
    "code": "code",
    "sup": "sup",
    "sub": "sub",
}
_ALLOWED_TAGS = {
    *_STYLES.values(),
    *_DECORATORS.values(),
    "ul",
    "ol",
    "li",
    "a",
    "br",
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
    blank: bool = False


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
        attribute_filter=_resize_images,
    )


def _resize_images(tag: str, attribute: str, value: str) -> str:
    # Pasted and rich-text images alike, so neither can fail the Webflow write.
    return resized(value) if (tag, attribute) == ("img", "src") else value


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
                out.append(f'<figure><img src="{escape(block.url)}" alt="{alt}"></figure>')
        else:
            tag = _STYLES.get(block.style, "p")
            out.append(f"<{tag}>{_inline(block)}</{tag}>")
    while lists:
        out.append(f"</li></{lists.pop()}>")
    return sanitize("".join(out))


def _inline(block: TextBlock) -> str:
    links = {d.key: d for d in block.mark_defs if d.href}
    html = ""
    for span in block.children:
        text = escape(span.text).replace("\n", "<br>")
        for mark in span.marks:
            if tag := _DECORATORS.get(mark):
                text = f"<{tag}>{text}</{tag}>"
            elif link := links.get(mark):
                # nh3's `link_rel` adds the noopener rel itself.
                target = ' target="_blank"' if link.blank else ""
                text = f'<a href="{escape(link.href or "")}"{target}>{text}</a>'
        html += text
    return html


# A rich text report has no pages to gate at; by default it opens its first quarter.
RICH_PREVIEW_SHARE = 0.25
_GATE = "<div data-wusool-gate></div>"
_TAG = re.compile(r"<[^>]+>")
# Fonts load in the reader's iframe and, through the renderer's allow-list, in the PDF.
_RICH_HEAD = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400..700&display=swap">'
    "<style>@page{size:A4;margin:20mm 18mm}"
    ".wusool-rich{padding:32px 24px;font:17px/1.7 'DM Sans',sans-serif;color:#000523}"
    ".wusool-rich h1{font-size:36px;line-height:1.2;margin:0 0 24px}"
    ".wusool-rich h2{font-size:26px;line-height:1.3;margin:36px 0 12px}"
    ".wusool-rich h3{font-size:21px;margin:28px 0 10px}"
    ".wusool-rich h4{font-size:18px;margin:24px 0 8px}"
    ".wusool-rich h5{font-size:16px;margin:20px 0 8px}"
    ".wusool-rich h6{font-size:14px;margin:20px 0 8px;text-transform:uppercase;"
    "letter-spacing:.04em}"
    ".wusool-rich code{font:.9em ui-monospace,monospace;padding:1px 4px;border-radius:3px;"
    "background:rgba(0,5,35,.06)}"
    ".wusool-rich sup,.wusool-rich sub{font-size:.75em;line-height:0}"
    ".wusool-rich p,.wusool-rich ul,.wusool-rich ol{margin:0 0 16px}"
    ".wusool-rich blockquote{margin:24px 0;padding-left:16px;border-left:3px solid rgba(0,5,35,.2)}"
    ".wusool-rich figure{margin:24px 0}.wusool-rich img{max-width:100%;height:auto}"
    ".wusool-rich a{color:inherit}"
    "@media print{.wusool-rich{padding:0}}</style></head><body>"
)


def rich_report(title: str, blocks: list[Block], share: float = RICH_PREVIEW_SHARE) -> str | None:
    """A whole page for a report written in the rich text editor, its gate
    marked at about `share` of the text. Never cuts inside a list."""
    units: list[list[Block]] = []
    for block in blocks:
        if _listed(block) and units and _listed(units[-1][-1]):
            units[-1].append(block)
        else:
            units.append([block])
    parts = [to_html(unit) for unit in units]
    sizes = [len(_TAG.sub("", part)) for part in parts]
    if not sum(sizes):
        return None
    body: list[str] = []
    read = 0
    for part, size in zip(parts, sizes, strict=True):
        # Never before the first block, so the preview is never empty.
        if body and _GATE not in body and read >= sum(sizes) * share:
            body.append(_GATE)
        body.append(part)
        read += size
    return (
        f'{_RICH_HEAD}<article class="wusool-rich"><h1>{escape(title)}</h1>'
        f"{''.join(body)}</article></body></html>"
    )


def _listed(block: Block) -> bool:
    return isinstance(block, TextBlock) and block.list_item is not None
