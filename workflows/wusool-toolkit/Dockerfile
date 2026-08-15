# syntax=docker/dockerfile:1

# Builder: resolve/install dependencies with uv, using the workspace
# lockfile so the image gets exactly what CI/local dev tested against.
# This replaces matching-engine's and ddl-commands' own (now-deleted)
# per-folder Dockerfiles — one merged process, one image.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Workspace member manifests first, separate from source code, so editing
# app code doesn't invalidate this layer's cache.
COPY pyproject.toml uv.lock ./
COPY matching-engine/pyproject.toml matching-engine/pyproject.toml
COPY ddl-commands/pyproject.toml ddl-commands/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY main.py ./main.py
COPY matching-engine/app matching-engine/app
COPY ddl-commands/ddl_commands ddl-commands/ddl_commands
# --no-editable: workspace members are installed as real copies into the
# venv's site-packages, not path-referencing shims back to /app/matching-engine
# and /app/ddl-commands — the runtime stage below never copies those source
# directories at all, only the venv and main.py.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


# Runtime: no uv, no build tools, no tests — just the venv and the entrypoint.
FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --from=builder --chown=app:app /app/main.py ./main.py

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

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
