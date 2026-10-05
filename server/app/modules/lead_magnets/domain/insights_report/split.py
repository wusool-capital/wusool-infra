"""Cuts a report into the free preview and the gated rest. Pure.

The cut always falls on the end of a top-level block, so neither half splits
a paragraph or a table. `preview + rest` is the original string, unchanged:
the page re-renders both together on unlock, which restores any wrapper the
cut left open in the preview.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser

PREVIEW_SHARE = 0.25

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


@dataclass
class _Node:
    tag: str
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
        self.root = _Node("#root", 0, 0)
        self._stack = [self.root]
        self._text = 0
        self._muted = 0

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        content_start = self._offset() + len(self.get_starttag_text() or "")
        node = _Node(tag, self._text, content_start)
        self._stack[-1].children.append(node)
        if tag in _VOID:
            node.end, node.text_end = content_start, self._text
            return
        self._stack.append(node)
        if tag in _NO_TEXT:
            self._muted += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        end = self._offset() + len(self.get_starttag_text() or "")
        self._stack[-1].children.append(_Node(tag, self._text, end, end, self._text))

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
    return [child for child in node.children if child.tag not in _NO_TEXT]


def split_report(html: str, share: float = PREVIEW_SHARE) -> tuple[str, str]:
    """`(preview, rest)`. A report with no second block to cut after keeps
    everything gated: the preview is then only what precedes the content."""
    parser = _Tree(html)
    parser.feed(html)
    tree = parser.finish()

    root = _find(tree, "body") or tree
    while len(blocks := _blocks(root)) == 1:
        root = blocks[0]
    if len(blocks) < 2:
        return html[: root.content_start], html[root.content_start :]

    target = root.text_start + share * (root.text_end - root.text_start)
    candidates = blocks[:-1]  # cutting after the last block would gate nothing
    cut = next((block for block in candidates if block.text_end >= target), candidates[-1]).end
    return html[:cut], html[cut:]
