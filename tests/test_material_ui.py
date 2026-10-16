"""The wrapper pages are styled with the vendored Material Web bundle.

Issue #21 asks for `@material/web` on the server-rendered pages. These tests
pin that the bundle is served and that login, home, and admin pages actually
load it and use `md-*` components rather than bare HTML controls.
"""

from box_of_twine.users import create_user


def login_as(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def test_material_bundle_is_served(client):
    response = client.get("/static/material/material.js")

    assert response.status_code == 200
    assert response.mimetype == "text/javascript"
    assert b"customElements" in response.data


def test_login_page_uses_material_components(client):
    html = client.get("/login").data

    assert b"/static/material/material.js" in html
    assert b"md-outlined-text-field" in html
    assert b"md-filled-button" in html


def test_authenticated_pages_use_material_components(app, client):
    with app.app_context():
        create_user("ada", "ada-password", is_admin=True)
    login_as(client, "ada", "ada-password")

    home = client.get("/")
    assert home.status_code == 200
    assert b"/static/material/material.js" in home.data
    assert b"md-outlined-text-field" in home.data
    assert b"md-filled-button" in home.data

    admin = client.get("/admin/users")
    assert admin.status_code == 200
    assert b"md-outlined-text-field" in admin.data
    assert b"md-checkbox" in admin.data
