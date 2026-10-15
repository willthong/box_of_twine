# Work order

Base commit: `0d84c87dd9fe6eaf2353208cb3cf2604b173f231` (branch `main`).

Ordered vertical slices. Each entry names the ticket and the public interface
(the seam) it is tested at. Non-slice work items are marked and dispatched as a
single build step.

| # | Ticket | Seam | Kind |
|---|--------|------|------|
| 1 | [#12 Slice 1 — Admin can log in](issue-12.md) | `POST /login` | slice |
| 2 | [#13 Slice 2 — Admin manages users](issue-13.md) | `POST /users`, `PATCH /users/<id>`, `DELETE /users/<id>` | slice |
| 3 | [#14 Slice 3 — User manages their stories](issue-14.md) | `POST /stories`, `GET /stories`, `DELETE /stories/<id>` | slice |
| 4 | [#22 Spike — Vendor the twinejs build](issue-22.md) | built SPA served as static assets | spike (prereq for slice 4) |
| 5 | [#15 Slice 4 — Open a story in the editor](issue-15.md) | `GET /edit/<story_id>`, `GET /stories/<story_id>` | slice |
| 6 | [#16 Slice 5 — Save story edits](issue-16.md) | `PUT /stories/<story_id>` | slice |
| 7 | [#17 Slice 6 — Share: viewer](issue-17.md) | `POST /stories/<story_id>/shares` | slice |
| 8 | [#18 Slice 7 — Share: editor + owner](issue-18.md) | `POST /stories/<story_id>/shares` (role escalation) | slice |
| 9 | [#19 Slice 8 — Edit lock](issue-19.md) | `POST /stories/<story_id>/lock` | slice |
| 10 | [#20 Slice 9 — Publish](issue-20.md) | `POST /stories/<story_id>/publications`, `GET /p/<slug>` | slice |
| 11 | [#21 Slice 10 — Theme toggle](issue-21.md) | `PATCH /prefs` | slice |
| 12 | [#23 CI/CD — pytest + GHCR](issue-23.md) | workflow + Dockerfile | infra |

Excluded: #11 "v2 backlog" is deferred, not a v1 work item.
