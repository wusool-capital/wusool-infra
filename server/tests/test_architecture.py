"""Cross-module architecture fitness tests — per the `/modular-monolith`
skill's cross-module rules. Complements each module's own
`tests/test_architecture.py` (which only checks a module's `domain/`/
`application/` against its *own* `persistence/`/`providers/`/`api/`).

Three checks:

1. `test_cross_module_import_boundaries` — a module may reach into another
   module's `domain/` freely (shared-kernel exception: pure, framework-free
   logic), or into its bare root (`app.modules.<other>`, checked separately
   against `__all__` below). Reaching into another module's `persistence/`,
   `providers/`, `api/`, or `temporal/` is forbidden UNLESS the target is one
   of `_FULL_ACCESS_MODULES` — `utilities`, `attio`, and `organizations` are
   all documented, deliberate exceptions (see their own `__init__.py`
   docstrings): modules with no domain layer whose entire surface (a single
   concrete repository, for `organizations`) is legitimately constructed
   directly by consumers, unlike business modules that must go through
   `domain/`-only or allowlisted `application/ports/` imports.
   `application/ports/` imports
   across modules are the risky exception the skill calls out — allowed only
   via the explicit `_APPLICATION_PORTS_ALLOWLIST` below; currently empty,
   since every existing cross-module Port-typed reference in this repo
   (e.g. `ddl_commands/application/ports/unit_of_work.py` importing
   `OrganizationRepositoryPort`) imports it from the target's *root*
   `__init__.py`, not a deep `application.ports` path.
2. `test_cross_module_root_imports_only_use_public_all` — an import that
   targets a module's bare root (`app.modules.<module>`, nothing deeper)
   must only name symbols listed in that module's own `__all__`.
3. `test_module_dependency_graph_is_acyclic` — no module may (transitively)
   depend on a module that depends back on it.
"""

import ast
from pathlib import Path

MODULES_ROOT = Path(__file__).parent.parent / "app" / "modules"

_FULL_ACCESS_MODULES = {"utilities", "attio", "organizations"}
_APPLICATION_PORTS_ALLOWLIST: set[tuple[str, str]] = set()
_FORBIDDEN_LAYERS = ("persistence", "providers", "api", "temporal")


def _module_names() -> list[str]:
    return sorted(
        p.name
        for p in MODULES_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith("__") and (p / "__init__.py").exists()
    )


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _own_module_all(module: str) -> set[str]:
    init_path = MODULES_ROOT / module / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                return {
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                }
    return set()


def _module_source_files(module: str) -> list[Path]:
    return [
        path
        for path in (MODULES_ROOT / module).rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]


def test_cross_module_import_boundaries() -> None:
    modules = _module_names()
    violations: dict[str, list[str]] = {}
    for module in modules:
        for path in _module_source_files(module):
            for dotted in _imports(path):
                if not dotted.startswith("app.modules."):
                    continue
                rest = dotted[len("app.modules.") :].split(".")
                target = rest[0]
                if target == module:
                    continue  # same-module import, not cross-module
                if target not in modules:
                    continue
                sub_parts = rest[1:]
                if not sub_parts:
                    continue  # bare root import — checked separately below
                layer = sub_parts[0]
                if layer == "domain":
                    continue  # shared-kernel exception
                key = str(path.relative_to(MODULES_ROOT.parent))
                if layer == "application":
                    if len(sub_parts) >= 2 and sub_parts[1] == "ports":
                        if (module, target) in _APPLICATION_PORTS_ALLOWLIST:
                            continue
                        violations.setdefault(key, []).append(dotted)
                    continue
                if layer in _FORBIDDEN_LAYERS:
                    if target in _FULL_ACCESS_MODULES:
                        continue
                    violations.setdefault(key, []).append(dotted)
    assert violations == {}


def test_cross_module_root_imports_only_use_public_all() -> None:
    modules = _module_names()
    module_alls = {m: _own_module_all(m) for m in modules}
    violations: dict[str, list[str]] = {}
    for module in modules:
        for path in _module_source_files(module):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if not node.module.startswith("app.modules."):
                    continue
                rest = node.module[len("app.modules.") :].split(".")
                target = rest[0]
                if target == module or target not in modules or len(rest) != 1:
                    continue  # not a bare-root import, or same-module
                imported_names = {alias.name for alias in node.names}
                disallowed = imported_names - module_alls[target]
                if disallowed:
                    violations.setdefault(str(path.relative_to(MODULES_ROOT.parent)), []).extend(
                        sorted(disallowed)
                    )
    assert violations == {}


def test_module_dependency_graph_is_acyclic() -> None:
    modules = _module_names()
    graph: dict[str, set[str]] = {m: set() for m in modules}
    for module in modules:
        for path in _module_source_files(module):
            for dotted in _imports(path):
                if not dotted.startswith("app.modules."):
                    continue
                target = dotted[len("app.modules.") :].split(".")[0]
                if target in modules and target != module:
                    graph[module].add(target)

    visiting: set[str] = set()
    visited: set[str] = set()
    cycle: list[str] = []

    def _visit(node: str, path: list[str]) -> bool:
        if node in visiting:
            cycle.extend([*path, node])
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in graph[node]:
            if _visit(dep, [*path, node]):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    for module in modules:
        if module not in visited and _visit(module, []):
            break

    assert cycle == [], f"circular module dependency: {' -> '.join(cycle)}"
