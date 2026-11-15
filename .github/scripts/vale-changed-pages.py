#!/usr/bin/env python3
"""Runs Vale on the documentation pages this branch changed and fails on any
warning in them, the same way CI's reviewdog `filter_mode: file` does. Whole
pages must pass because the push to dev and prod lints whole pages."""

import json
import os
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
    "gitbook/technical-documentation",
    "gitbook/operations-and-handover",
    "gitbook/release-notes",
]


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


def changed_pages(base: str) -> list[str]:
    """Pages changed since `base`, including uncommitted and untracked files."""
    changed = git("diff", "--name-only", "--diff-filter=d", base, "--", *TARGETS).split()
    changed += git("ls-files", "--others", "--exclude-standard", "--", *TARGETS).split()
    return sorted({path for path in changed if path.endswith(".md")})


def main() -> int:
    if shutil.which("vale") is None:
        print("vale is not installed (brew install vale); skipping docs check", file=sys.stderr)
        return 0
    root = Path(git("rev-parse", "--show-toplevel").strip())
    try:
        os.chdir(root)
        pages = changed_pages(merge_base())
        if not pages:
            print("vale: no documentation changes to check")
            return 0
        run = subprocess.run(
            ["vale", "--output=JSON", "--minAlertLevel=warning", *pages],
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
    ]
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
