"""Architecture fitness test: `domain/` and `application/` (excluding their own
`tests/`) may only import stdlib and each other — never `providers/`, `.api`,
`fastapi`, `pydantic`, `httpx`, `sqlalchemy` or `google`. The one thing this
module must never do is import a consumer: `interactions` and Scribe depend on
it, so a dependency back would be a cycle.
"""

import ast
from pathlib import Path

_MODULE_ROOT = Path(__file__).parent.parent
_CHECKED_LAYERS = ("domain", "application")
_FORBIDDEN_PREFIXES = (
    "app.modules.google_workspace.providers",
    "app.modules.google_workspace.api",
    "fastapi",
    "pydantic",
    "httpx",
    "sqlalchemy",
    "google",
)
_CONSUMERS = ("app.modules.interactions", "app.modules.meetings")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _starts_with(dotted: str, prefixes: tuple[str, ...]) -> bool:
    return any(dotted == prefix or dotted.startswith(prefix + ".") for prefix in prefixes)


def test_domain_and_application_dependencies_point_inward() -> None:
    violations: dict[str, list[str]] = {}
    for layer in _CHECKED_LAYERS:
        layer_root = _MODULE_ROOT / layer
        for path in layer_root.rglob("*.py"):
            found = [name for name in _imports(path) if _starts_with(name, _FORBIDDEN_PREFIXES)]
            if found:
                violations[str(path.relative_to(_MODULE_ROOT))] = found
    assert violations == {}


def test_the_module_never_imports_a_consumer() -> None:
    violations: dict[str, list[str]] = {}
    for path in _MODULE_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        found = [name for name in _imports(path) if _starts_with(name, _CONSUMERS)]
        if found:
            violations[str(path.relative_to(_MODULE_ROOT))] = found
    assert violations == {}
