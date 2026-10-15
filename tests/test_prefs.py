"""Slice 10 — theme toggle. Seam: `PATCH /prefs`.

Rendering contract these tests pin down: a wrapper page's `<html>` element
carries `data-theme="dark"` when the logged-in user has chosen the dark theme.
With no stored preference the page forces nothing, leaving
`prefers-color-scheme` to decide.
"""

import re

from box_of_twine.users import create_user


def login_as(client, user):
    return client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )


def html_theme(page: bytes) -> str | None:
    match = re.search(rb"<html\b[^>]*\bdata-theme=\"([^\"]+)\"", page)
    return match.group(1).decode() if match is not None else None


def test_toggling_dark_persists_per_user_and_next_render_emits_dark_theme(
    app, client, admin
):
    with app.app_context():
        create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.patch("/prefs", json={"theme": "dark"})
    assert response.status_code in (200, 204)

    # The next render of a wrapper page emits the dark theme.
    assert html_theme(client.get("/login").data) == "dark"

    # The choice survives a new session, so it is persisted, not session-only.
    fresh = app.test_client()
    login_as(fresh, admin)
    assert html_theme(fresh.get("/login").data) == "dark"

    # It is per-user: bob's render is unaffected by admin's choice.
    other = app.test_client()
    login_as(other, {"username": "bob", "password": "bob-password"})
    assert html_theme(other.get("/login").data) != "dark"


def test_default_theme_follows_prefers_color_scheme(app, client):
    with app.app_context():
        create_user("bob", "bob-password")

    login_as(client, {"username": "bob", "password": "bob-password"})
    page = client.get("/login").data

    # No stored preference: the server forces no theme...
    assert html_theme(page) != "dark"
    # ...and defers to the browser's color-scheme preference instead.
    assert b"prefers-color-scheme: dark" in page
