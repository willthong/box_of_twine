from pathlib import Path

from box_of_twine.db import get_db
from box_of_twine.users import create_user


def login_as(client, user):
    return client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )


def test_admin_creates_user_who_can_log_in(client, admin):
    login_as(client, admin)

    response = client.post("/users", json={"username": "bob", "password": "bob-password"})
    assert response.status_code == 201

    response = client.post("/login", data={"username": "bob", "password": "bob-password"})
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session.get("_user_id") is not None
        assert session.get("_user_id") != str(admin["id"])


def test_non_admin_cannot_create_user(app, client):
    with app.app_context():
        create_user("bob", "bob-password")

    response = client.post("/login", data={"username": "bob", "password": "bob-password"})
    assert response.status_code == 302

    response = client.post(
        "/users", json={"username": "carol", "password": "carol-password"}
    )
    assert response.status_code == 403


def test_disabled_user_cannot_log_in(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.patch(f"/users/{bob_id}", json={"disabled": True})
    assert response.status_code == 200

    response = client.post("/login", data={"username": "bob", "password": "bob-password"})
    assert response.status_code == 401


def test_deleting_user_removes_their_stories(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    story = Path(app.config["DATA_DIR"]) / "users" / str(bob_id) / "stories" / "1.json"
    story.parent.mkdir(parents=True, exist_ok=True)
    story.write_text("{}")

    login_as(client, admin)
    response = client.delete(f"/users/{bob_id}")
    assert response.status_code == 204

    assert not story.exists()


def test_admin_resets_user_password(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "old-password")

    login_as(client, admin)
    response = client.patch(f"/users/{bob_id}", json={"password": "new-password"})
    assert response.status_code == 200

    response = client.post("/login", data={"username": "bob", "password": "old-password"})
    assert response.status_code == 401

    response = client.post("/login", data={"username": "bob", "password": "new-password"})
    assert response.status_code == 302


def test_admin_can_grant_and_revoke_admin(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.patch(f"/users/{bob_id}", json={"is_admin": True})
    assert response.status_code == 200

    # The granted admin can now use an admin-only endpoint.
    bob = app.test_client()
    login_as(bob, {"username": "bob", "password": "bob-password"})
    response = bob.post(
        "/users", json={"username": "carol", "password": "carol-password"}
    )
    assert response.status_code == 201

    # Revoking the grant takes the admin powers away again.
    response = client.patch(f"/users/{bob_id}", json={"is_admin": False})
    assert response.status_code == 200
    response = bob.post("/users", json={"username": "dave", "password": "dave-password"})
    assert response.status_code == 403


def test_deleting_user_cascades_their_stories_shares_and_publications(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")
        carol_id = create_user("carol", "carol-password")

    source = Path(app.config["DATA_DIR"]) / "users" / str(bob_id) / "stories" / "1.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}")

    with app.app_context():
        db = get_db()
        cursor = db.execute(
            "INSERT INTO stories (owner_id, name) VALUES (?, ?)", (bob_id, "Bob's Story")
        )
        story_id = cursor.lastrowid
        db.execute(
            "INSERT INTO shares (story_id, user_id, role) VALUES (?, ?, ?)",
            (story_id, carol_id, "viewer"),
        )
        db.execute(
            "INSERT INTO publications (story_id, slug, visibility, html) "
            "VALUES (?, ?, ?, ?)",
            (story_id, "bob-story", "public", "<html></html>"),
        )
        # A share granting bob access to someone else's story.
        other = db.execute(
            "INSERT INTO stories (owner_id, name) VALUES (?, ?)",
            (carol_id, "Carol's Story"),
        )
        db.execute(
            "INSERT INTO shares (story_id, user_id, role) VALUES (?, ?, ?)",
            (other.lastrowid, bob_id, "editor"),
        )
        db.commit()

    login_as(client, admin)
    response = client.delete(f"/users/{bob_id}")
    assert response.status_code == 204

    with app.app_context():
        db = get_db()
        for table in ("shares", "publications"):
            count = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE story_id = ?", (story_id,)
            ).fetchone()[0]
            assert count == 0, f"{table} row for the deleted user's story must be gone"
        assert (
            db.execute(
                "SELECT COUNT(*) FROM stories WHERE id = ?", (story_id,)
            ).fetchone()[0]
            == 0
        )
        incoming = db.execute(
            "SELECT COUNT(*) FROM shares WHERE user_id = ?", (bob_id,)
        ).fetchone()[0]
        assert incoming == 0, "shares granted to the deleted user must be gone"
        assert (
            db.execute("SELECT COUNT(*) FROM users WHERE id = ?", (bob_id,)).fetchone()[0]
            == 0
        )
    assert not source.exists()
