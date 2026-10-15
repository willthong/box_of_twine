# Issue #20: Slice 9 — Publish

Vertical slice, red → green. **Seam:** `POST /stories/<story_id>/publications`, `GET /p/<slug>`.

- Compile server-side in Python (story JSON + story format source → standalone HTML via `{{STORY_DATA}}`/`{{STORY_NAME}}`); see `docs/adr/0002-server-side-story-compilation.md`.
- Visibility: `private` (owner) / `shared` (named users) / `public` (anyone with URL). Managing publications (incl. public) requires `owner`.
- Test: publish compiles HTML containing the story data; `GET /p/<slug>` serves it; public is reachable anonymously, private is denied to others.
