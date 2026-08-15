"""Empty on purpose — its only job is to make pytest add this directory to
`sys.path`, so `tests/integration/test_merged_command_dispatch.py`'s
`import main` resolves. `tests/` here deliberately has no `__init__.py`
(same for `ddl-commands/tests/`) — matching-engine's `tests/` is the only
one that still is a package, since it's the only project with test files
doing an absolute `from tests.fakes... import ...`. All three projects'
`tests/` directories share the top-level name `tests` and now sit on the
same `sys.path` (via this workspace's editable installs, which expose each
member's whole project root, not just its package) — only one can safely be
a real importable package without colliding.
"""
