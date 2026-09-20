"""Reject verbose Python comments before they reach the repository."""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

MAX_COMMENT_CHARS = 88
MAX_COMMENT_WORDS = 20
_WORD = re.compile(r"\b[\w'-]+\b")
_SKIPPED_DIRECTIVES = ("noqa", "type:", "pyright:")


def main() -> int:
    server_root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for path in sorted(server_root.rglob("*.py")):
        if ".venv" in path.parts:
            continue
        try:
            tokens = tokenize.tokenize(io.BytesIO(path.read_bytes()).readline)
            comments = (token for token in tokens if token.type == tokenize.COMMENT)
            for token in comments:
                body = token.string[1:].strip()
                if not body or body.startswith(_SKIPPED_DIRECTIVES):
                    continue
                words = len(_WORD.findall(body))
                if len(token.string) > MAX_COMMENT_CHARS or words > MAX_COMMENT_WORDS:
                    relative = path.relative_to(server_root)
                    failures.append(
                        f"{relative}:{token.start[0]}: comment is "
                        f"{len(token.string)} chars/{words} words "
                        f"(limits: {MAX_COMMENT_CHARS} chars/{MAX_COMMENT_WORDS} words)"
                    )
        except (SyntaxError, UnicodeDecodeError, tokenize.TokenError) as error:
            failures.append(f"{path}: unable to tokenize Python source: {error}")

    if failures:
        print("Python comments must explain why, briefly:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Python comment quality passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
