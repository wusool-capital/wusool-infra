"""Architecture fitness test: `domain/` and `application/` (excluding their
own `tests/`) may only import stdlib, `domain/`, and `application/ports/` —
never `persistence/`, `providers/`, `.api`, `fastapi`, `pydantic`, or
`sqlalchemy`. Concrete implementations are wired in only by `bootstrap.py`/
`api/dependencies.py`.

`pydantic` alone has one deliberate, narrow exception: `domain/shared/
schemas.py` types the shapes stored in `tool_runs.payload` (see that file's
own docstring for why). Nothing else in `domain/`/`application/` gets this —
the allowlist is a path, not a package, so a second file cannot piggyback on
it silently.
"""

import ast
from pathlib import Path

_MODULE_ROOT = Path(__file__).parent.parent
_CHECKED_LAYERS = ("domain", "application")
_FORBIDDEN_PREFIXES = (
    "app.modules.lead_magnets.persistence",
    "app.modules.lead_magnets.providers",
    "app.modules.lead_magnets.api",
    "fastapi",
    "pydantic",
    "sqlalchemy",
)
_PYDANTIC_ALLOWED_PATHS = frozenset({"domain/shared/schemas.py"})


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
            relative = str(path.relative_to(_MODULE_ROOT))
            allow_pydantic = relative in _PYDANTIC_ALLOWED_PATHS
            found = [
                name
                for name in _imports(path)
                if _is_forbidden(name) and not (allow_pydantic and name == "pydantic")
            ]
            if found:
                violations[relative] = found
    assert violations == {}


def test_pydantic_allowlist_names_a_real_file() -> None:
    """A stale entry here would silently stop enforcing anything — this
    keeps the allowlist honest."""
    for relative in _PYDANTIC_ALLOWED_PATHS:
        assert (_MODULE_ROOT / relative).is_file(), relative
