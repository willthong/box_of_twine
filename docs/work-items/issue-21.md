# Issue #21: Slice 10 — Theme toggle

Vertical slice, red → green. **Seam:** `PATCH /prefs`.

- Dark/light toggle persisted per-user, default follows `prefers-color-scheme`.
- Test: toggling dark persists, and the next page render emits the dark theme.

Material styling of wrapper pages (`@material/web` v2.5) is applied incrementally within each slice; this slice is specifically the toggle.
