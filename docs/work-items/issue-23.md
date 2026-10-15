# Issue #23: CI/CD — pytest + publish container to GHCR

GitHub Actions workflow, runs on push and PR:

- Job `test`: `pytest` (gating), plus `ruff check` (line-length 90) and `ty` typecheck.
- Job `container`: build the Docker image and push to **GHCR as a public package** on `main` and tags.

Image: `python:3.14-slim`, gunicorn serving app + static, named volume for `/data`. gunicorn declares support only through 3.13; if it misbehaves on 3.14, fall back to uvicorn via `asgiref`'s `WsgiToAsgi`. Document env vars: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`.
