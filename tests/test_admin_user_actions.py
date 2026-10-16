"""Slice 5 — admin user actions. Seam: form POSTs under ``/admin/users``.

The admin users page's action forms post URL-encoded data. Creating a user,
updating one (an optional password plus the ``disabled``/``is_admin``
checkboxes), and deleting one all redirect back to the users list with 303 so
the browser lands on the refreshed page. The same auth rules as the page itself
apply to every POST: an anonymous visitor is sent to ``/login``, an
authenticated non-admin is refused with 403, and a refused request changes
nothing.
"""

from pathlib import Path
from urllib.parse import urlsplit

from box_of_twine.db import get_db
from box_of_twine.users import create_user


def login_as(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def redirect_target(response):
    return urlsplit(response.headers["Location"]).path


def test_form_post_creates_a_user_who_can_log_in(app, client, admin):
    login_as(client, admin["username"], admin["password"])

    response = client.post(
        "/admin/users",
        data={"username": "bob", "password": "bob-password"},
    )

    assert response.status_code == 303
    assert redirect_target(response) == "/admin/users"

    # A fresh client proves the new user is real, not just a session swap.
    bob = app.test_client()
    assert login_as(bob, "bob", "bob-password").status_code == 302
    with bob.session_transaction() as session:
        assert session.get("_user_id") is not None


def test_form_post_can_create_an_admin(app, client, admin):
    login_as(client, admin["username"], admin["password"])

    response = client.post(
        "/admin/users",
        data={"username": "zoe", "password": "zoe-password", "is_admin": "on"},
    )

    assert response.status_code == 303

    zoe = app.test_client()
    assert login_as(zoe, "zoe", "zoe-password").status_code == 302
    assert zoe.get("/admin/users").status_code == 200


def test_form_post_disables_a_user_who_cannot_log_in(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    login_as(client, admin["username"], admin["password"])
    response = client.post(f"/admin/users/{bob_id}/update", data={"disabled": "on"})

    assert response.status_code == 303
    assert redirect_target(response) == "/admin/users"

    bob = app.test_client()
    assert login_as(bob, "bob", "bob-password").status_code == 401


def test_form_post_re_enables_a_disabled_user(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    login_as(client, admin["username"], admin["password"])
    disabled = client.post(f"/admin/users/{bob_id}/update", data={"disabled": "on"})
    assert disabled.status_code == 303

    # An unchecked checkbox is simply absent from the form body.
    enabled = client.post(f"/admin/users/{bob_id}/update", data={})
    assert enabled.status_code == 303

    bob = app.test_client()
    assert login_as(bob, "bob", "bob-password").status_code == 302


def test_form_post_reads_explicit_checkbox_values(app, client, admin):
    """The admin form always submits both boxes, so a value of ``off`` unchecks."""
    with app.app_context():
        bob_id = create_user("bob", "bob-password", is_admin=True)

    login_as(client, admin["username"], admin["password"])
    # A browser sends the hidden fallback and, when checked, the box's value.
    cleared = client.post(
        f"/admin/users/{bob_id}/update",
        data={"is_admin": ["off"], "disabled": ["off"]},
    )
    assert cleared.status_code == 303

    bob = app.test_client()
    login_as(bob, "bob", "bob-password")
    assert bob.get("/admin/users").status_code == 403

    restored = client.post(
        f"/admin/users/{bob_id}/update",
        data={
            "is_admin": ["off", "on"],
            "disabled": ["off", "on"],
        },
    )
    assert restored.status_code == 303

    fresh = app.test_client()
    assert login_as(fresh, "bob", "bob-password").status_code == 401


def test_form_post_resets_a_users_password(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "old-password")

    login_as(client, admin["username"], admin["password"])
    response = client.post(
        f"/admin/users/{bob_id}/update", data={"password": "new-password"}
    )

    assert response.status_code == 303

    bob = app.test_client()
    assert login_as(bob, "bob", "old-password").status_code == 401
    assert login_as(bob, "bob", "new-password").status_code == 302


def test_form_post_grants_and_revokes_admin(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    login_as(client, admin["username"], admin["password"])
    granted = client.post(f"/admin/users/{bob_id}/update", data={"is_admin": "on"})
    assert granted.status_code == 303

    bob = app.test_client()
    login_as(bob, "bob", "bob-password")
    assert bob.get("/admin/users").status_code == 200

    revoked = client.post(f"/admin/users/{bob_id}/update", data={})
    assert revoked.status_code == 303

    assert bob.get("/admin/users").status_code == 403


def test_form_post_deletes_a_user_and_their_content(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")
        carol_id = create_user("carol", "carol-password")

    source = Path(app.config["DATA_DIR"]) / "users" / str(bob_id) / "stories" / "1.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}")

    with app.app_context():
        db = get_db()
        story_id = db.execute(
            "INSERT INTO stories (owner_id, name) VALUES (?, ?)",
            (bob_id, "Bob's Story"),
        ).lastrowid
        db.execute(
            "INSERT INTO shares (story_id, user_id, role) VALUES (?, ?, ?)",
            (story_id, carol_id, "viewer"),
        )
        db.execute(
            "INSERT INTO publications (story_id, slug, visibility, html) "
            "VALUES (?, ?, ?, ?)",
            (story_id, "bob-story", "public", "<html></html>"),
        )
        db.commit()

    login_as(client, admin["username"], admin["password"])
    response = client.post(f"/admin/users/{bob_id}/delete")

    assert response.status_code == 303
    assert redirect_target(response) == "/admin/users"

    with app.app_context():
        db = get_db()
        for table, column, value in (
            ("users", "id", bob_id),
            ("stories", "id", story_id),
            ("shares", "story_id", story_id),
            ("publications", "story_id", story_id),
        ):
            count = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (value,)
            ).fetchone()[0]
            assert count == 0, f"{table} row for the deleted user must be gone"
    assert not source.exists()


def test_anonymous_form_posts_redirect_to_login_and_change_nothing(app, client):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")
        before = get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]

    for url, data in (
        ("/admin/users", {"username": "mallory", "password": "mallory-password"}),
        (f"/admin/users/{bob_id}/update", {"disabled": "on"}),
        (f"/admin/users/{bob_id}/delete", {}),
    ):
        response = client.post(url, data=data)
        assert response.status_code == 302, url
        assert redirect_target(response) == "/login", url

    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == before
        assert (
            db.execute("SELECT COUNT(*) FROM users WHERE id = ?", (bob_id,)).fetchone()[0]
            == 1
        )

    bob = app.test_client()
    assert login_as(bob, "bob", "bob-password").status_code == 302


def test_non_admin_form_posts_are_forbidden_and_change_nothing(app, client):
    with app.app_context():
        create_user("bob", "bob-password")
        carol_id = create_user("carol", "carol-password")
        before = get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]

    login_as(client, "bob", "bob-password")

    create_response = client.post(
        "/admin/users", data={"username": "mallory", "password": "mallory-password"}
    )
    update_response = client.post(
        f"/admin/users/{carol_id}/update", data={"disabled": "on"}
    )
    delete_response = client.post(f"/admin/users/{carol_id}/delete")

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert delete_response.status_code == 403

    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == before
        assert (
            db.execute("SELECT COUNT(*) FROM users WHERE id = ?", (carol_id,)).fetchone()[
                0
            ]
            == 1
        )

    carol = app.test_client()
    assert login_as(carol, "carol", "carol-password").status_code == 302
