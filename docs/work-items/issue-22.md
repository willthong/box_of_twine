# Issue #22: Spike — Vendor the twinejs build

Non-TDD spike, prerequisite for slice 4.

- Fork klembot/twinejs at a pinned release; build the static `dist/`; serve it from Flask as static assets.
- Bundle the four stock story formats: Harlowe, SugarCube, Snowman, Chapbook.
- License GPL-3.0; see `docs/adr/0001-fork-twinejs-with-http-persistence.md`.
- The in-browser persistence backend and the "being edited by X" banner are wired to the HTTP seams in slices 5 and 8.
