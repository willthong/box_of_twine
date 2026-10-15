# Issue #19: Slice 8 — Edit lock

Vertical slice, red → green. **Seam:** `POST /stories/<story_id>/lock`.

- Per-story pessimistic lease: acquired on entering edit mode; ~10-minute lease renewed by activity; released on close or lapse; force-break by owner/admin.
- Server-enforced: `PUT` by a non-holder → 409 (the fork surfaces "story is being edited by X").
- Reads/play are never blocked.
- Test: two editors — the second `PUT` returns 409 while the first holds the lock; owner force-break then allows it.
