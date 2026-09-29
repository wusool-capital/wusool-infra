#!/usr/bin/env python3
"""Runs Vale on the documentation the CI job checks and fails only on
warnings that sit on lines this branch added or changed, the same way CI's
reviewdog filter does. Existing warnings elsewhere in a page don't block."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Mirrors `files:` in .github/workflows/docs-quality.yml.
TARGETS = [
    "CHANGELOG.md",
    "gitbook/README.md",
    "gitbook/SUMMARY.md",
    "gitbook/user-guide",
    "gitbook/technical",
    "gitbook/operations",
    "gitbook/deliverables",
]
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def merge_base() -> str:
    for ref in ("origin/dev", "dev"):
        result = subprocess.run(
            ["git", "merge-base", "HEAD", ref], capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    sys.exit("vale check: cannot find origin/dev or dev to compare against")


def added_lines(base: str) -> dict[str, set[int]]:
    """Lines added since `base`, including uncommitted and untracked files."""
    added: dict[str, set[int]] = {}
    path = ""
    for line in git("diff", "-U0", base, "--", *TARGETS).splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif match := HUNK.match(line):
            start, count = int(match[1]), int(match[2] or 1)
            added.setdefault(path, set()).update(range(start, start + count))
    for path in git("ls-files", "--others", "--exclude-standard", "--", *TARGETS).split():
        total = len(Path(path).read_text(encoding="utf-8").splitlines())
        added[path] = set(range(1, total + 1))
    return added


def main() -> int:
    if shutil.which("vale") is None:
        print("vale is not installed (brew install vale); skipping docs check", file=sys.stderr)
        return 0
    root = Path(git("rev-parse", "--show-toplevel").strip())
    try:
        os.chdir(root)
        added = added_lines(merge_base())
        if not added:
            print("vale: no documentation changes to check")
            return 0
        run = subprocess.run(
            ["vale", "--output=JSON", "--minAlertLevel=warning", *added],
            capture_output=True,
            text=True,
        )
        alerts = json.loads(run.stdout or "{}")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"vale check: git failed: {exc.stderr}")

    failures = [
        f"{path}:{alert['Line']} {alert['Message']} [{alert['Check']}]"
        for path, path_alerts in alerts.items()
        for alert in path_alerts
        if alert["Line"] in added.get(path, set())
    ]
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
