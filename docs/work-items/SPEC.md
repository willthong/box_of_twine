# Box of Twine — shared spec

A self-hosted, multi-user web app that vendors the Twine editor, stores each
user's stories on the server, lets users share stories with each other, and
publishes compiled stories to the web. The README, `GLOSSARY.md`, and the ADRs
in `docs/adr/` are authoritative for domain vocabulary and architecture; use
their exact terms.

## Architecture (from the ADRs)

- **Vendored editor** (`docs/adr/0001-fork-twinejs-with-http-persistence.md`):
  fork `klembot/twinejs` (GPL-3.0) at a pinned release, serve its built `dist/`
  from Flask, and add a persistence backend that talks to our REST API instead
  of `localStorage`.
- **Server-side compilation** (`docs/adr/0002-server-side-story-compilation.md`):
  publications are produced in Python by substituting `{{STORY_NAME}}` and
  `{{STORY_DATA}}` into the story-format HTML. Do not run Node or the browser
  to compile.

## Stack

- Python, managed with `uv`. Ruff with **line-length 90** and `ty` typecheck.
- Flask app factory. Flask-Login signed-cookie sessions. Werkzeug `scrypt`
  password hashing.
- SQLite accessed with raw SQL for metadata; story *source* lives on disk.
- Pytest tests that exercise the HTTP seams with the Flask test client.
- Target deploy image `python:3.14-slim`, served by gunicorn, named volume at
  `/data`. Env vars: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`.

## Data layout

- Each story's source is one JSON file at
  `/data/users/<user_id>/stories/<story_id>.json`.
- The SQLite `stories` table holds metadata only. Shares, publications, locks,
  and prefs are metadata tables too.
- Users, stories, shares, publications, locks, prefs are the domain nouns
  (see `GLOSSARY.md`).

## Roles

`viewer` (read-only) · `editor` (read + edit) · `owner` (read + edit + share +
publish + delete + transfer). Multiple co-equal owners per story.

## Conventions

- Every ticket is a vertical slice tested at its stated seam. Keep the seam
  stable; add only what the test forces.
- Domain terms: use the glossary's words (`story`, `passage`, `share`, `role`,
  `lock`, `publication`, `visibility`) and avoid its listed synonyms.
