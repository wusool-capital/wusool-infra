"""Architecture fitness test: `application/` (excluding its own `tests/`)
may only import stdlib, `domain/`, and `application/ports/` — never
`persistence/`, `providers/`, `.api`, `fastapi`, `pydantic`, or
`sqlalchemy`. Concrete implementations are wired in only by `bootstrap.py`/
`api/dependencies.py`. No `domain/` layer here by design — this bot has no
matching pipeline (see `application/ports/buyers.py`'s docstring).
"""

import ast
from pathlib import Path

_MODULE_ROOT = Path(__file__).parent.parent
_CHECKED_LAYERS = ("domain", "application")
_FORBIDDEN_PREFIXES = (
    "app.modules.ddl_commands.persistence",
    "app.modules.ddl_commands.providers",
    "app.modules.ddl_commands.api",
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


def _is_forbidden(dotted: str) -> bool:
    return any(
        dotted == prefix or dotted.startswith(prefix + ".") for prefix in _FORBIDDEN_PREFIXES
    )


def test_domain_and_application_dependencies_point_inward() -> None:
    violations: dict[str, list[str]] = {}
    for layer in _CHECKED_LAYERS:
        layer_root = _MODULE_ROOT / layer
        if not layer_root.is_dir():
            continue
        for path in layer_root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            found = [name for name in _imports(path) if _is_forbidden(name)]
            if found:
                violations[str(path.relative_to(_MODULE_ROOT))] = found
    assert violations == {}
