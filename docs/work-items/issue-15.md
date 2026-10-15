# Issue #15: Slice 4 — Open a story in the editor

Vertical slice, red → green. **Seam:** `GET /edit/<story_id>`, `GET /stories/<story_id>`.

- Serve the vendored Twine SPA at `/edit/<story_id>` (depends on the vendor spike).
- Test: the route serves the editor page; the story endpoint returns the story JSON to an authorized user (and 404/403 otherwise).

Note: read-only-vs-edit rendering is enforced by `PUT` authorization (slices 5–6), not this slice.
