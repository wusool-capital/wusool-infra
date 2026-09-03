# syntax=docker/dockerfile:1

# Builder: resolve/install dependencies with uv, using the project's
# lockfile so the image gets exactly what CI/local dev tested against.
# One project now (server/) — no uv workspace, no path dependency to a
# separate database package, so this build context can just be `server/`
# itself instead of the repo root.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY main.py ./main.py
COPY app ./app
# --no-editable: the project is installed as a real copy into the venv's
# site-packages, not a path-referencing shim back to its source directory —
# the runtime stage below never copies the source tree at all, only the venv
# and the entrypoint files it needs directly.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


# Runtime: no uv, no build tools, no tests — just the venv and the entrypoint.
FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --from=builder --chown=app:app /app/main.py ./main.py

# alembic.ini + alembic/ are plain config/data files, not part of the
# installed package (venv install above only copies Python package
# contents) — copied explicitly so `docker run <this image> python -m
# alembic upgrade head` works standalone. See .github/workflows/_deploy.yml's
# "Run pending database migrations" step, which runs exactly that, via SSM,
# against the toolkit EC2 instance (the only thing with a network path to
# the private RDS instance).
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app alembic ./alembic

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

CMD ["python", "main.py"]
