# Issue #12: Slice 1 — Admin can log in

Vertical slice, red → green. **Seam:** `POST /login` (Flask test client).

- First admin bootstrapped from `ADMIN_USERNAME` + `ADMIN_PASSWORD` env vars: create only if no admin exists; ignore if an admin already exists; fail loudly at startup if only one var is set.
- Werkzeug scrypt hashing; Flask-Login signed-cookie sessions.
- Test: admin logs in (session cookie set); bad password → 401.

This slice forces the skeleton: uv/ruff (line-length 90)/ty, app factory, `users` table (raw SQL), login page.
