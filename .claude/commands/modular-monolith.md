# Modular Monolith Structure Guide

Canonical layout for a module/app in this codebase. Modeled on `server/app/modules/crm`
in lokamspace. Follow this exactly — do not invent alternative layer names or folders.

This document itself is intentionally long and detailed — that's fine for a reference an
agent consults, since the detail is what prevents predictable mistakes. It is not a
template: the `README.md`/`HOW-TO-TEST.md` you generate per module should stay short and
concrete, not mirror this document's length or level of exposition.

## Top-level module shape

```
&lt;module&gt;/
  __init__.py
  config.py            # pydantic-settings, nothing else
  bootstrap.py          # composition root — see "Composition root" below
  .env.example
  pyproject.toml
  README.md
  HOW-TO-TEST.md
  domain/
  application/
  persistence/
  providers/
  api/
  scripts/
  temporal/             # ONLY if the module actually needs durable execution — do not add speculatively
  tests/                # cross-cutting/integration tests + the architecture test (see below)
```

Every layer folder (`domain/`, `application/`, `persistence/`, `providers/`, `api/`,
`scripts/`, `temporal/`) gets its own `tests/` subfolder for unit tests colocated with
that layer. The top-level `tests/` is for integration tests that span layers, plus
`test_architecture.py`.

## File-per-concept escalation rule

A domain concept (e.g. `buyers`, `matching`, `attio_sync`) starts as **one file**:

```
domain/buyers.py
application/buyers.py
persistence/repositories/buyers.py
```

Only split a file into a subfolder once it is genuinely too long to read comfortably:

```
domain/matching/
  __init__.py
  entities.py       # dataclasses / value objects / enums
  lifecycle.py       # pure business rules, state transitions
  provider.py          # plain value objects related to this concept (NOT abstract ports — see below)
  tests/
```

Never split preemptively "for consistency." One file per concept is the default.

## Layer responsibilities

### `domain/`
Framework-free business rules only. Entities, value objects, enums, `Literal`s, pure
functions over them.

- **No** `pydantic`, **no** `sqlalchemy`, **no** `fastapi`, **no** `temporalio` imports. Ever.
- **No** abstract Ports here — a common mistake. `domain/provider.py` is a plain enum/value
  object (e.g. `class CRMProvider(StrEnum): ...`), not a `Protocol`.
- Depends on nothing else in *this module's own* `persistence/`, `providers/`, `api/`, or
  `temporal/`.
- Importing another module's `domain/` is fine and normal when that module's domain is
  pure, framework-free logic being reused as a de facto shared kernel — e.g. `crm`,
  `data_ingestion`, and `notifications` all import `app.modules.enrichment.domain.*`
  directly (phone/email/name normalization). This is not a layering violation; it's the
  established way pure logic gets shared across modules in this codebase.
- **This has a governance cost the fitness tests can't catch, because it's a judgment
  call, not a syntactic rule.** Cross-module `domain/` imports are only for genuinely
  generic, framework-free primitives (normalization, formatting, pure calculations) that
  carry no ownership or business behavior specific to the providing module. If a module's
  `domain/` starts accumulating things like `enrich_contact()` or `resolve_company()` —
  behavior that expresses *that module's* business rules rather than a generic
  primitive — new modules reaching into it are a shared-kernel-dumping-ground smell, not a
  green light. Treat every *new* cross-module `domain/` dependency as a moment to ask "is
  this actually generic," not as an automatically-approved pattern just because the
  layer-level rule allows it mechanically.

### `application/`
Use-case orchestration. Consumes `domain/` types and `application/ports/` Protocols only.

```
application/
  base.py               # ServiceBase — shared constructor/state (injected Ports) for every concern mixin below
  &lt;concern&gt;.py            # one file per functional concern (events.py, writeback.py, reporting.py, integrations.py, ...)
                             # each defines a mixin class subclassing ServiceBase with that concern's use-case methods
  service.py                # THIN facade only: combines every concern mixin via multiple inheritance into one class
  errors.py                   # application-level exceptions
  provider_errors.py            # exceptions specific to provider/adapter failures
  ports/
    repository.py                 # abstract Protocol — what persistence/ must implement
    provider.py                      # abstract Protocol — what providers/ must implement
    workflows.py                       # abstract Protocol — what temporal/ must implement
    provider_types.py                    # dataclasses/TypedDicts referenced by the Protocols above
  tests/
```

**`service.py` contains no business logic of its own.** It is exactly this and nothing
more:

```python
class CRMService(IntegrationService, EventService, ReportingService, WritebackService):
    """Compose CRM application use cases behind one module facade."""
```

Each mixin (`WritebackService`, `EventService`, ...) lives in its own `&lt;concern&gt;.py` file
and subclasses `ServiceBase` from `base.py`, which owns the one shared `__init__`
(injected Ports like `providers`/`workflows`) so no concern file redeclares its own
constructor. Nothing outside `service.py` imports the individual concern files directly —
`bootstrap.py`, `api/dependencies.py`, and temporal activities only ever construct and
call the single composed `&lt;Module&gt;Service` class from `service.py`.

When adding a new use-case area, add a new `&lt;concern&gt;.py` mixin subclassing `ServiceBase`
and add it to the inheritance list in `service.py` — don't grow `service.py` itself with
new methods, and don't let other layers import a concern file directly.

**This `base.py` + per-concern mixin + facade split is `crm`'s answer to having several
substantial, independently testable concern areas (events, writeback, reporting,
integrations) — it is not a mandatory shape for every module.** A module with one
cohesive use-case area doesn't need to be forced into `base.py` + multiple mixins +
multiple inheritance; a single `service.py` with its own class and methods is the correct,
simpler starting point, per the file-per-concept escalation rule above. Reach for the
mixin split only once a module's `application/` genuinely has multiple concern areas
substantial enough to warrant separate files and separate constructors' worth of shared
state — the same "don't split preemptively" judgment that applies everywhere else in this
guide.

**Hard rule, enforced by an architecture test (see below): `application/` must never
import `persistence/`, `providers/`, `api/`, `temporal/`, `fastapi`, `pydantic`, or
`sqlalchemy` directly.** It only knows about `application/ports/*` Protocols. Concrete
implementations are injected by `bootstrap.py` (or passed in by whatever composition
root calls the use case) — never imported inline inside a use case function.

This is the rule most agents get wrong: they'll write `application/buyers.py` importing
`persistence.repositories.buyers_repository.BuyerRepository` directly because "it needs
a repository." It doesn't — it takes a `BuyerRepositoryPort` as a constructor/function
argument, and something outside `application/` supplies the real one.

### `persistence/`
Talks to *our own* database. Implements `application/ports/repository.py`.

```
persistence/
  base.py
  mappers.py              # ORM row &lt;-&gt; domain entity translation — do not inline this in repositories
  models/                   # SQLAlchemy models OWNED by this module only
  repositories/               # one file per concept, implements the Port
  tests/
```

If a model is shared across modules, it does not belong in `&lt;module&gt;/persistence/models/`
— it belongs in the shared top-level models package, same as this repo's `app/models`.
Only module-private tables go in `persistence/models/`.

**A model being importable from `app.models` does not grant cross-module data access.**
`app.models.Customer` being available to every module doesn't mean every module may
query or mutate the `Customer` table — ownership of a table belongs to whichever
module's use cases are responsible for its lifecycle, and other modules should still go
through that module's public capability (its `__init__.py` facade) rather than issuing
their own queries against a table they don't own, even when the ORM model is sitting
right there in a shared import. Treat `app.models` as "the shared vocabulary for talking
about these entities," not "a shared database access layer."

### `providers/`
Talks to *third-party* APIs/services. Implements `application/ports/provider.py`. This is
the layer most often wrongly merged with `persistence/` — keep "our DB" and "their API"
physically separate.

```
providers/
  registry.py                   # maps a provider enum -&gt; concrete adapter, if there's more than one provider
  &lt;vendor&gt;/                       # one subpackage per external provider
    adapter.py                      # implements the Port
    auth.py
    client.py
    errors.py
    mapping.py
    protocol.py
    schemas/                          # Pydantic models scoped to parsing THIS vendor's payloads only
      __init__.py
    tests/
  tests/
```

Pydantic is allowed here — but only to parse one vendor's request/response shape. It
never leaks back into `domain/` or `application/`.

### `api/`
Presentation/entry adapter. FastAPI routers, HTTP schemas, webhook handlers.

```
api/
  schemas.py           # shared Pydantic request/response DTOs for this module
  router.py              # aggregates the routers below
  &lt;concept&gt;.py             # route handlers for one concept/integration (webhooks.py, vinsolutions.py, ...)
  dependencies.py            # FastAPI Depends()-style WIRING — see note below
  tests/
```

**`schemas.py` and `dependencies.py` are not the same thing and are easy to confuse:**

- `schemas.py` = pure `pydantic.BaseModel` data definitions. No `fastapi`, no
  `Depends()`, no session/repository construction. If a file only defines `BaseModel`
  classes (even if it validates LLM output, webhook payloads, whatever), it is a
  `schemas.py`-shaped file, not a `dependencies.py`-shaped one.
- `dependencies.py` = glue/composition code for endpoints: `Depends()` providers, rate
  limiting, auth/session lookups, code that constructs a repository/service and calls
  into `application/`. It imports `fastapi`, often `sqlalchemy`, and application-layer
  commands. No data-class definitions belong here.

A module missing `dependencies.py` doesn't need one invented until it actually has
endpoint-wiring logic to extract out of route handlers.

### `scripts/`
One-off/admin scripts for this module. Own `tests/`.

### `temporal/` (only when actually used)
Do not add this speculatively. If the module has no durable-execution need, skip it —
adding empty `activities/`/`workflows/` folders "for consistency with crm" is exactly the
kind of speculative structure to avoid.

```
temporal/
  activities/
  workflows/
  contracts/          # payload types for activities/workflows
  search_attributes.py
  starter.py
  tests/
```

## Cross-module imports (when there is more than one module/app)

This only applies once there is more than one top-level module/app that needs to talk to
another (e.g. lokamspace's `app/modules/crm`, `enrichment`, `data_ingestion`, ...). If
you're building a single module/app in isolation, skip this section.

There is **no dedicated "public API" folder** for this in the existing codebase — do not
invent one (e.g. `public/`, `contracts/`). The real, working convention is:

- **Only the symbols a module explicitly exports via `__all__` in its top-level
  `__init__.py` are its supported cross-module contract** — not "anything importable from
  the module." See `enrichment/__init__.py`, which exports `EnrichmentService` plus a
  handful of domain types/functions via `__all__`. Other modules import from that barrel
  (`from app.modules.enrichment import EnrichmentService`) rather than reaching into
  `enrichment.application.service` directly. Adding something to `__all__` is a deliberate
  compatibility commitment, not an accident of what happens to be importable.
  **Concretely: a cross-module import that targets the module root
  (`app.modules.&lt;module&gt;`, nothing deeper) must only name symbols listed in that module's
  `__all__`.** `__all__` isn't a Python access-control mechanism — Python will happily let
  `from app.modules.foo import _internal_thing` succeed even though `_internal_thing`
  isn't exported. That doesn't make it allowed: treat `__all__` as the conceptual contract
  regardless of what the language itself permits, and rely on the test below — not on
  Python — to actually turn "not exported" into "not importable across modules."
- **Cross-module `domain/` imports are fine and common** for pure, framework-free logic
  (see the note in the `domain/` section above). Treat another module's `domain/` as a
  shared kernel when it's genuinely just pure functions/value objects. This is safe by
  construction: every module's `domain/` is already required to be framework-free and free
  of its own module's other layers, so depending on it can't smuggle in coupling to
  another module's persistence/providers/api.
- **Cross-module `application/ports/` imports are the risky exception, not a general
  allowance.** The default is: don't do this — go through the owning module's `__init__.py`
  facade instead. The only reason it's tolerated at all today is one explicit, already-existing
  case (`data_ingestion/application/ports/` wrapping `enrichment`'s
  `NormalizationServicePort` to compose an adapter). Do not treat "application/ports imports
  are fine" as a general pattern to reach for — each new instance couples your module to
  another module's internal contract surface, which is exactly what the Ports pattern
  exists to prevent *within* a module. If you think you need a new one, that's a signal to
  either widen the owning module's `__init__.py` public surface instead, or treat it as a
  deliberate, reviewed architectural decision — not a default move. Any new instance must
  be added to the explicit allowlist in the architecture test below; an unlisted
  cross-module `application.ports` import should fail the test.
- **Never import another module's `persistence/`, `providers/`, `api/`, or `temporal/`.**
  Each module owns its own tables, its own vendor adapters, its own HTTP surface, and its
  own durable workflows exclusively through those folders. This is enforced by the
  cross-module architecture test below, not just stated as intent.
- **Never import anything under another module's `application/` except
  `application/ports/`** (and even that only per the allowlist above). Reaching into
  `billing.application.service` or any other concrete application file from outside its
  own module bypasses the Port discipline the same way reaching into its `persistence/`
  would — the test below treats it as the same class of violation.
- **Each module gets its own `bootstrap.py`.** There is no single global composition root
  wiring every module together. A module's `bootstrap.py` may import *another* module's
  public `__init__.py` facade to construct its own dependencies (as `data_ingestion`'s
  does with `enrichment`), but it never reaches into another module's `persistence/` or
  `providers/` to do so.
- Keep `application/ports/provider_types.py` limited to types that represent *this
  module's* contract with a provider. Don't let a vendor-specific schema from
  `providers/&lt;vendor&gt;/schemas/` leak into `application/` — map it to a
  `provider_types.py` type at the adapter boundary first.

### When `application/` code needs another module's capability

This is the one case the rules above don't settle on their own: if `orders/application/checkout.py`
needs something from `billing`, does it call `billing`'s public facade directly, or go
through a locally-defined Port the way it would for its own module's `persistence/`?

Both are legitimate, and the choice depends on what kind of dependency it is:

- **If the use case's own business logic genuinely depends on that capability** — it's
  something the use case needs to be substitutable or testable independent of the real
  `billing` implementation, or the use case's correctness meaningfully depends on how it
  behaves — define a Port in `orders/application/ports/` (e.g. `PaymentPort`), have
  `orders/bootstrap.py` adapt `billing`'s public `BillingService` to that Port, and have
  `checkout.py` depend only on the Port, exactly like it would for its own persistence:

  ```
  orders.application.checkout
          │  depends on
          ▼
  orders.application.ports.PaymentPort
          ▲  implemented by an adapter constructed in
          │
  orders.bootstrap
          │  wraps
          ▼
  billing (public __init__.py facade)
  ```

- **If it's a simple, incidental call to another module's stable public capability** —
  not a core dependency of the use case's own logic, nothing that needs to be swapped out
  or mocked independently — calling `billing`'s public facade directly is fine. Don't
  force a Port + adapter for every cross-module call just for consistency; that's
  architecture astronautics, not the pattern this codebase actually uses. A Port earns its
  keep when it's decoupling something that matters, not by default.

The current `tests/test_architecture.py` pattern (see below) does **not** check any of
this on its own — it only checks a module's own layers against its own
framework/persistence/providers imports. If you're introducing multiple modules that need
to interoperate, add the cross-module test in the next section. A documented rule that
nothing enforces is not a rule an agent will actually follow — write the test, don't just
describe the intent.

## Composition root: `bootstrap.py`

`bootstrap.py` is the *only* place that is allowed to import concrete `persistence/` and
`providers/` classes and wire them into `application/` use cases (e.g. building a
`create_app()` FastAPI factory, or a factory function `api/dependencies.py` calls). Route
handlers and Temporal activities should go through this wiring rather than each
constructing their own repository/adapter instances inline in `api/dependencies.py` — if
you see repository/adapter construction duplicated in multiple `dependencies.py`/activity
files, that construction belongs in `bootstrap.py` as a shared factory instead.

## Type placement — quick reference

| Type kind | Lives in |
|---|---|
| `pydantic.BaseModel` | `api/schemas.py`, `api/&lt;concept&gt;.py`; or `providers/&lt;vendor&gt;/schemas/*.py` (vendor payload parsing) |
| `dataclass` / `enum` / `Literal` | `domain/entities.py` (or concept file); `application/ports/provider_types.py` for port-adjacent types |
| Abstract `Protocol`/`ABC` (a Port) | `application/ports/*.py` — never `domain/` |
| SQLAlchemy model | `persistence/models/*.py` only |

`domain/` and `application/` never contain `pydantic` or `sqlalchemy` imports — full stop.

## Required: architecture fitness test

Every module must have `tests/test_architecture.py` enforcing the dependency-direction
rule mechanically, not just in prose. Minimum check:

```python
def test_domain_and_application_dependencies_point_inward() -&gt; None:
    forbidden = (
        "app.core",
        "app.modules.&lt;module&gt;.api",
        "app.modules.&lt;module&gt;.persistence",
        "app.modules.&lt;module&gt;.providers",
        "app.modules.&lt;module&gt;.temporal",
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "temporalio",
    )
    # walk every .py file under domain/ and application/ (excluding their tests/),
    # parse imports via ast, assert none start with anything in `forbidden`
```

This is what actually prevents drift back into the old tangled structure — don't skip it
as "just docs."

### Cross-module fitness test (only once there's more than one module)

The within-module test above says nothing about *other* modules. Add two more tests that
fail closed by default. `_imports` here is the same AST helper as above — it must resolve
both `import app.modules.foo.persistence.models` and
`from app.modules.foo.persistence.models import Bar` to the same dotted string,
`"app.modules.foo.persistence.models"`.

A **bare** `import app.modules.&lt;other&gt;` (naming only the package root, three dotted
segments, nothing deeper) is deliberately allowed and not flagged by either test below —
it doesn't name any specific internal symbol, so it can't bypass `__all__` the way naming
a deeper attribute or importing a specific name would.

```python
# Explicit, reviewed allowlist of the only permitted cross-module application/ports
# imports. Anything not listed here is a violation — see the "risky exception" rule
# in the cross-module imports section. Add to this list only as a deliberate decision,
# not as a default way to reuse another module's port.
ALLOWED_CROSS_MODULE_PORT_IMPORTS = {
    ("data_ingestion", "enrichment"),  # DataIngestion wraps EnrichmentNormalizationAdapter
}


def test_cross_module_import_boundaries() -&gt; None:
    """Enforce: other.__init__ / other.domain OK; other.application.ports allowlisted
    only; everything else cross-module (persistence, providers, api, temporal, and any
    application file that isn't ports) is forbidden."""
    violations: dict[str, str] = {}
    for module_dir in MODULES_ROOT.iterdir():
        if not module_dir.is_dir():
            continue
        this_module = module_dir.name
        for path in module_dir.rglob("*.py"):
            if "tests" in path.parts:
                continue
            for dotted in _imports(path):
                if not dotted.startswith("app.modules."):
                    continue
                parts = dotted.split(".")
                other_module = parts[2]
                if other_module == this_module:
                    continue
                if len(parts) == 3:
                    continue  # bare root import — allowed, see note above
                other_layer = parts[3]
                if other_layer == "domain":
                    continue  # shared-kernel exception — governed by review, not this test
                if other_layer == "application" and len(parts) &gt;= 5 and parts[4] == "ports":
                    if (this_module, other_module) in ALLOWED_CROSS_MODULE_PORT_IMPORTS:
                        continue
                    violations[str(path)] = f"{dotted} (application.ports import not in allowlist)"
                    continue
                # persistence / providers / api / temporal / application.&lt;anything-but-ports&gt;
                violations[str(path)] = dotted
    assert violations == {}


def _module_all(init_path: Path) -&gt; list[str]:
    if not init_path.is_file():
        return []
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            return [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)]
    return []


def test_cross_module_root_imports_only_use_public_all() -&gt; None:
    """Enforce: `from app.modules.&lt;other&gt; import X` only names symbols in &lt;other&gt;'s
    __all__ — the one case test_cross_module_import_boundaries can't see, since a
    bare-root import doesn't carry a symbol name to check."""
    violations: dict[str, str] = {}
    for module_dir in MODULES_ROOT.iterdir():
        if not module_dir.is_dir():
            continue
        this_module = module_dir.name
        for path in module_dir.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                parts = node.module.split(".")
                if len(parts) != 3 or parts[:2] != ["app", "modules"]:
                    continue
                other_module = parts[2]
                if other_module == this_module:
                    continue
                public = set(_module_all(module_dir.parent / other_module / "__init__.py"))
                imported_names = {alias.name for alias in node.names}
                if not imported_names &lt;= public:
                    violations[str(path)] = f"{node.module}: {imported_names - public}"
    assert violations == {}
```

Together these two tests encode the full matrix:

```
A → B.__init__ (bare import, or `from` naming only __all__ symbols)   allowed
A → B.domain                                                          allowed (shared kernel)
A → B.application.ports                                               allowlist only
A → B.persistence / .providers / .api / .temporal                     forbidden
A → B.application.&lt;anything but ports&gt;                                forbidden
```

### Recommended: module dependency graph must stay acyclic

Neither test above catches `A → B` and `B → A` existing at the same time (even through
otherwise-allowed edges, e.g. both importing each other's `domain/`). A cycle between
modules means neither can be understood, tested, or extracted without the other, which
defeats the point of splitting them in the first place. This is a recommendation, not a
hard architectural law — some codebases tolerate cycles deliberately — but as of this
writing every real cross-module edge in this repo already points toward `enrichment`
(which imports no other module back), so the graph is already acyclic and this costs
nothing to enforce going forward:

```python
def _module_dependency_graph() -&gt; dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for module_dir in MODULES_ROOT.iterdir():
        if not module_dir.is_dir():
            continue
        this_module = module_dir.name
        deps: set[str] = set()
        for path in module_dir.rglob("*.py"):
            if "tests" in path.parts:
                continue
            for dotted in _imports(path):
                if not dotted.startswith("app.modules."):
                    continue
                other_module = dotted.split(".")[2]
                if other_module != this_module:
                    deps.add(other_module)
        graph[this_module] = deps
    return graph


def test_module_dependency_graph_is_acyclic() -&gt; None:
    graph = _module_dependency_graph()
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle: list[str] = []

    def visit(node: str, path: list[str]) -&gt; bool:
        if node in visiting:
            cycle.extend([*path[path.index(node) :], node])
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in graph.get(node, ()):
            if visit(dep, [*path, node]):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    for module in graph:
        if module not in visited and visit(module, []):
            break

    assert not cycle, f"Cyclic module dependency: {' -&gt; '.join(cycle)}"
```

If two modules genuinely need each other, that's usually a sign they're one module split
in the wrong place, or that one of them should be talking through a third module/event
mechanism instead of directly.

## Summary of the most common mistakes to avoid

1. Putting an abstract Port in `domain/*/provider.py` instead of `application/ports/*.py`.
2. Letting `application/` import `persistence/`/`providers/` directly instead of only
   `application/ports/` Protocols, injected via `bootstrap.py`.
3. Confusing a pure-schema file (`api/schemas.py`-shaped) with `dependencies.py`
   (wiring/glue) just because both live under `api/`.
4. Merging "talks to our DB" and "talks to a third-party API" into one `infrastructure/`
   folder instead of separate `persistence/` and `providers/`.
5. Adding `temporal/`, subfolders, or extra layer files speculatively before a concept
   actually needs them.
6. Skipping `tests/test_architecture.py` and relying on code review alone to catch
   layering violations.
7. Inventing a `public/`/`contracts/` folder for cross-module boundaries — this codebase's
   actual convention is a curated `__init__.py` `__all__` barrel per module.
8. Reaching into another module's `persistence/` or `providers/` instead of going through
   its public `__init__.py` facade.
