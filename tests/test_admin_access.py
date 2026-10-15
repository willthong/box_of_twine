"""Admin has full access to everything (GLOSSARY).

The admin-only `/users` seams are covered in ``test_users.py``. These tests pin
the other half of the admin flag: an admin who neither owns a story nor holds a
share on it still passes every story access check — read, write, share,
publish, and delete.
"""

from box_of_twine.users import create_user

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "passages": [
        {"name": "Start", "text": "You wake in a garden of brass."},
        {"name": "Gate", "text": "A gate hums with clockwork."},
    ],
}


def login_as(client, user):
    return client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )


def test_admin_without_ownership_or_share_has_full_story_access(app, admin):
    with app.app_context():
        create_user("bob", "bob-password")
        carol_id = create_user("carol", "carol-password")

    # Bob owns the story; the admin neither owns it nor holds a share on it.
    bob = app.test_client()
    login_as(bob, {"username": "bob", "password": "bob-password"})
    response = bob.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    admin_client = app.test_client()
    login_as(admin_client, admin)

    # Read.
    response = admin_client.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == NEW_STORY

    # Open the editor.
    assert admin_client.get(f"/edit/{story_id}").status_code == 200

    # Write.
    edited = {**NEW_STORY, "name": "Admin's Edit"}
    assert admin_client.put(f"/stories/{story_id}", json=edited).status_code == 200
    assert admin_client.get(f"/stories/{story_id}").get_json()["name"] == "Admin's Edit"

    # Share.
    response = admin_client.post(
        f"/stories/{story_id}/shares", json={"user_id": carol_id, "role": "viewer"}
    )
    assert response.status_code == 201

    # Publish.
    response = admin_client.post(
        f"/stories/{story_id}/publications", json={"visibility": "public"}
    )
    assert response.status_code == 201
    slug = response.get_json()["slug"]
    assert admin_client.get(f"/p/{slug}").status_code == 200

    # Delete.
    assert admin_client.delete(f"/stories/{story_id}").status_code == 204
    assert admin_client.get(f"/stories/{story_id}").status_code == 404
