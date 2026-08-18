# syntax=docker/dockerfile:1

# Builder: resolve/install dependencies with uv, using the workspace
# lockfile so the image gets exactly what CI/local dev tested against.
# This replaces matching-engine's and ddl-commands' own (now-deleted)
# per-folder Dockerfiles — one merged process, one image.
#
# Build context is the REPO ROOT, not this directory — matching-engine's and
# ddl-commands' pyproject.toml declare `wusool-db` as a uv path dependency
# via `../../../database` (three levels up from
# workflows/wusool-toolkit/<pkg>/), which only resolves correctly if that
# same directory nesting exists inside the image. Flattening the context to
# just this folder (the old approach, from before database/ existed as a
# separate top-level package) would break that path. See
# ALEMBIC_MIGRATION_HANDOVER.md point 6 and the root .dockerignore, which
# trims the wider context back down (.git/, terraform/, other workflows/,
# etc.) so this doesn't balloon build time.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# database/ first: it's a real (non-workspace) path dependency, not a
# workspace member, so `--no-install-project` below does NOT defer it — uv
# builds it from source during the very first sync. Workspace members
# (matching-engine/ddl-commands/shared) DO get deferred, since their source
# isn't copied in yet.
COPY database/pyproject.toml database/pyproject.toml
COPY database/wusool_db database/wusool_db

# Workspace member manifests next, separate from app source code, so editing
# app code doesn't invalidate this layer's cache.
COPY workflows/wusool-toolkit/pyproject.toml workflows/wusool-toolkit/uv.lock workflows/wusool-toolkit/
COPY workflows/wusool-toolkit/matching-engine/pyproject.toml workflows/wusool-toolkit/matching-engine/pyproject.toml
COPY workflows/wusool-toolkit/ddl-commands/pyproject.toml workflows/wusool-toolkit/ddl-commands/pyproject.toml
COPY workflows/wusool-toolkit/shared/pyproject.toml workflows/wusool-toolkit/shared/pyproject.toml

WORKDIR /app/workflows/wusool-toolkit
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY workflows/wusool-toolkit/main.py /app/workflows/wusool-toolkit/main.py
COPY workflows/wusool-toolkit/matching-engine/app /app/workflows/wusool-toolkit/matching-engine/app
COPY workflows/wusool-toolkit/ddl-commands/ddl_commands /app/workflows/wusool-toolkit/ddl-commands/ddl_commands
COPY workflows/wusool-toolkit/shared/toolkit_shared /app/workflows/wusool-toolkit/shared/toolkit_shared
# --no-editable: workspace members are installed as real copies into the
# venv's site-packages, not path-referencing shims back to their source
# directories — the runtime stage below never copies those source
# directories (or database/) at all, only the venv and main.py.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


# Runtime: no uv, no build tools, no tests — just the venv and the entrypoint.
FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/workflows/wusool-toolkit/.venv ./.venv
COPY --from=builder --chown=app:app /app/workflows/wusool-toolkit/main.py ./main.py
COPY --chown=app:app workflows/wusool-toolkit/run.py ./run.py

# alembic.ini + alembic/ are plain config/data files, not part of the
# installed wusool-db package (venv install above only copies Python
# package contents) — copied explicitly so `docker run <this image> python
# -m alembic -c database/alembic.ini upgrade head` works standalone. See
# .github/workflows/_deploy.yml's "Run pending database migrations" step,
# which runs exactly that, via SSM, against the toolkit EC2 instance (the
# only thing with a network path to the private RDS instance).
COPY --chown=app:app database/alembic.ini ./database/alembic.ini
COPY --chown=app:app database/alembic ./database/alembic

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

# /health has no database dependency (see main.py) — a healthy container
# only means the process is alive, not that the DB is reachable. Use
# /readiness separately (e.g. from an external check) if that distinction
# matters to your orchestrator.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["python", "run.py"]
