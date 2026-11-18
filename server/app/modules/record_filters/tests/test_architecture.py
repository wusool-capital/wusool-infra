"""Architecture fitness test: `domain/` may only import stdlib: never `persistence/`,
`api/`, `fastapi`, `pydantic` or `sqlalchemy`.
"""

import ast
from pathlib import Path

_MODULE_ROOT = Path(__file__).parent.parent
_FORBIDDEN_PREFIXES = (
    "app.modules.record_filters.persistence",
    "app.modules.record_filters.api",
    "fastapi",
    "pydantic",
    "sqlalchemy",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_domain_dependencies_point_inward() -> None:
    violations: dict[str, list[str]] = {}
    for path in (_MODULE_ROOT / "domain").rglob("*.py"):
        found = [
            name
            for name in _imports(path)
            if any(name == p or name.startswith(p + ".") for p in _FORBIDDEN_PREFIXES)
        ]
        if found:
            violations[str(path.relative_to(_MODULE_ROOT))] = found
    assert violations == {}
