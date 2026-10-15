# Issue #17: Slice 6 — Share: viewer

Vertical slice, red → green. **Seam:** `POST /stories/<story_id>/shares`.

- A share grants a role on a story. `viewer` = read-only (open editor read-only + play).
- Test: owner shares with a viewer; viewer can `GET` the story but `PUT` → 403.
