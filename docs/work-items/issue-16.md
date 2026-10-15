# Issue #16: Slice 5 — Save story edits

Vertical slice, red → green. **Seam:** `PUT /stories/<story_id>`.

- This is the HTTP persistence backend contract: the forked Twine editor saves the story (passages + metadata) through this endpoint; prefs and story formats ride the same mechanism.
- Test: GET → PUT → GET round-trips passages and metadata unchanged.
