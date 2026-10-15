# Issue #13: Slice 2 — Admin manages users

Vertical slice, red → green. **Seam:** `POST /users`, `PATCH /users/<id>`, `DELETE /users/<id>` (admin-only).

- Admin UI: create (username + initial password), disable, reset password, grant admin.
- Hard delete cascades: removes the user's stories, shares, publications. Disable is the reversible path (blocks login, keeps content).
- No self-registration.
- Tests: admin creates `bob` → `bob` logs in; non-admin create → 403; disabled user's login → 401; delete removes the user's stories; reset password works.
