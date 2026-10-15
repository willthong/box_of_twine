# Issue #14: Slice 3 — User manages their stories

Vertical slice, red → green. **Seam:** `POST /stories`, `GET /stories`, `DELETE /stories/<id>`.

- Hybrid storage: each story's source is one JSON file at `/data/users/<user_id>/stories/<story_id>.json`; SQLite `stories` table holds metadata only.
- Test: creating a story writes the JSON file and it appears in the owner's list (not another user's); rename updates it; delete removes the file and cascades shares/publications.
