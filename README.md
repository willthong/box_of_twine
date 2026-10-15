# box_of_twine
Self-hosted multi-user Twine: vendored editor, per-user story storage, sharing, and publication.

## Configuration

The app is configured through environment variables:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ADMIN_USERNAME` | no | unset | Username of the bootstrap admin. Must be set together with `ADMIN_PASSWORD`. |
| `ADMIN_PASSWORD` | no | unset | Password for the bootstrap admin. Must be set together with `ADMIN_USERNAME`. |
| `SECRET_KEY` | yes in production | `dev` | Signs the Flask-Login session cookies. Set a strong, random value in production; `dev` is a development placeholder. |
| `DATA_DIR` | no | `/data` | Root for on-disk story data. A story's source is `<DATA_DIR>/users/<user_id>/stories/<story_id>.json`. |

`ADMIN_USERNAME` and `ADMIN_PASSWORD` must both be set or both be unset; the
app fails loudly at startup otherwise. If both are set and no admin exists yet,
the admin is created.

Example:

```sh
ADMIN_USERNAME=admin \
ADMIN_PASSWORD=correct-horse-battery-staple \
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))') \
DATA_DIR=/data \
uv run gunicorn --bind 0.0.0.0:8000 'box_of_twine:create_app()'
```

## Container

```sh
docker build -t box-of-twine .
docker run --rm -p 8000:8000 \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=correct-horse-battery-staple \
  -e SECRET_KEY=change-me \
  -v box_of_twine_data:/data \
  box-of-twine
```

The image is based on `python:3.14-slim` and serves the Flask app and the
vendored editor with gunicorn on port 8000. It declares a named volume at
`/data` for story sources.
