# syntax=docker/dockerfile:1

# Runtime image for Box of Twine.
#
# Server: gunicorn. Its classifiers stop at Python 3.13, but 26.2.0 runs
# correctly on Python 3.14.8 (verified serving the app and the vendored
# editor's static assets), so no uvicorn/asgiref WsgiToAsgi fallback is used.
FROM python:3.14-slim

# Install uv from its official image for reproducible, lockfile-driven installs.
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/data

WORKDIR /app

# Install dependencies first so this layer is cached across source edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Install the project itself (including the vendored editor under
# src/box_of_twine/static/twine, which Flask serves).
COPY . .
RUN uv sync --frozen --no-dev

# Story sources live under /data/users/...; keep them on a named volume.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "4", "box_of_twine:create_app()"]
