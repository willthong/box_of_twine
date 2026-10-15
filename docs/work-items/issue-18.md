# Issue #18: Slice 7 — Share: editor + owner

Vertical slice, red → green. **Seam:** `POST /stories/<story_id>/shares` (role escalation).

Roles are cumulative: `viewer` (read) · `editor` (read + edit) · `owner` (read + edit + share + publish + delete + transfer).

- Multiple co-equal owners; "transfer" = grant `owner`.
- Test: an `editor` can `PUT`; an `owner` can share, delete the story, and grant `owner` to another user.
