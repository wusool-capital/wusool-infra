"""Cuts a report into the free preview and the gated rest. Pure.

The cut always falls between two blocks, so neither half splits a paragraph
or a table. It goes as deep as it must to land near the share: a block that
would overshoot it, such as one `<main>` holding the whole report, is cut
inside rather than after. `preview + rest` is the original string, unchanged:
the page re-renders both together on unlock, which restores any wrapper the
cut left open in the preview.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser

PREVIEW_SHARE = 0.25
# Set by the renderer on the block nearest 25% of the drawn height, a truer cut than text.
GATE_MARKER = "data-wusool-gate"
# How far past the share a cut may land before the crossing block is split instead.
_OVERSHOOT = 0.10

_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)
# Text in these never counts towards the share, and they are never a block to cut after.
_NO_TEXT = frozenset({"head", "title", "style", "script", "template", "noscript"})
# Cutting at these would split a paragraph mid-sentence.
_INLINE = frozenset(
    {
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "br",
        "cite",
        "code",
        "data",
        "del",
        "dfn",
        "em",
        "font",
        "i",
        "img",
        "ins",
        "kbd",
        "label",
        "mark",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "u",
        "var",
        "wbr",
    }
)


@dataclass
class _Node:
    tag: str
    start: int
    text_start: int
    content_start: int
    end: int = -1
    text_end: int = 0
    children: list["_Node"] = field(default_factory=list)


class _Tree(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self._html = html
        self._line_starts = [0] + [i + 1 for i, char in enumerate(html) if char == "\n"]
        self.root = _Node("#root", 0, 0, 0)
        self.gate_at: int | None = None
        self._stack = [self.root]
        self._text = 0
        self._muted = 0

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._offset()
        if self.gate_at is None and any(name == GATE_MARKER for name, _ in attrs):
            self.gate_at = start
        content_start = start + len(self.get_starttag_text() or "")
        node = _Node(tag, start, self._text, content_start)
        self._stack[-1].children.append(node)
        if tag in _VOID:
            node.end, node.text_end = content_start, self._text
            return
        self._stack.append(node)
        if tag in _NO_TEXT:
            self._muted += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._offset()
        end = start + len(self.get_starttag_text() or "")
        self._stack[-1].children.append(_Node(tag, start, self._text, end, end, self._text))

    def handle_endtag(self, tag: str) -> None:
        depth = next(
            (i for i in range(len(self._stack) - 1, 0, -1) if self._stack[i].tag == tag), 0
        )
        if not depth:
            return  # a stray end tag closes nothing
        end = self._html.index(">", self._offset()) + 1
        while len(self._stack) > depth:
            self._close(self._stack.pop(), end)

    def handle_data(self, data: str) -> None:
        if not self._muted:
            self._text += len(data.strip())

    def finish(self) -> _Node:
        self.close()
        while len(self._stack) > 1:
            self._close(self._stack.pop(), len(self._html))
        self._close(self.root, len(self._html))
        return self.root

    def _close(self, node: _Node, end: int) -> None:
        node.end, node.text_end = end, self._text
        if node.tag in _NO_TEXT:
            self._muted -= 1


def _find(node: _Node, tag: str) -> _Node | None:
    for child in node.children:
        if child.tag == tag:
            return child
        if (found := _find(child, tag)) is not None:
            return found
    return None


def _blocks(node: _Node) -> list[_Node]:
    return [c for c in node.children if c.tag not in _NO_TEXT and c.tag not in _INLINE]


def split_report(html: str, share: float = PREVIEW_SHARE) -> tuple[str, str]:
    """`(preview, rest)`. Cuts before the renderer's `GATE_MARKER` when present,
    else by text. When no cut can leave anything gated, everything is gated:
    the preview is then only what precedes the content."""
    parser = _Tree(html)
    parser.feed(html)
    tree = parser.finish()
    if parser.gate_at is not None:
        return html[: parser.gate_at], html[parser.gate_at :]

    body = _find(tree, "body") or tree
    total = body.text_end - body.text_start
    cut = _cut(body, body.text_start + share * total, _OVERSHOOT * total)
    return html[:cut], html[cut:]


def _cut(root: _Node, target: float, slack: float) -> int:
    blocks = _blocks(root)
    for i, block in enumerate(blocks):
        if block.text_end < target:
            continue
        is_last = i == len(blocks) - 1
        if not is_last and block.text_end - target <= slack:
            return block.end
        if _blocks(block):
            return _cut(block, target, slack)
        # A single block too big to split: cut before it, never after.
        return blocks[i - 1].end if i else root.content_start
    return blocks[-2].end if len(blocks) > 1 else root.content_start
