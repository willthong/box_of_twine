"""Story rename is available to editors and owners, not viewers.

Seam: `PATCH /stories/<story_id>`.
"""

import json
from pathlib import Path

from box_of_twine.users import create_user

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "passages": [{"name": "Start", "text": "You wake in a garden of brass."}],
}


def login_as(client, username):
    return client.post(
        "/login", data={"username": username, "password": f"{username}-password"}
    )


def signed_in(app, username):
    client = app.test_client()
    login_as(client, username)
    return client


def owned_story_with_role(app, admin, *, username, role):
    with app.app_context():
        user_id = create_user(username, f"{username}-password")

    owner = app.test_client()
    owner.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )
    response = owner.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    if role is not None:
        response = owner.post(
            f"/stories/{story_id}/shares", json={"user_id": user_id, "role": role}
        )
        assert response.status_code == 201
    return story_id


def source_path(app, user_id, story_id):
    return (
        Path(app.config["DATA_DIR"])
        / "users"
        / str(user_id)
        / "stories"
        / f"{story_id}.json"
    )


def test_editor_can_rename_a_story_and_the_listing_updates(app, admin):
    story_id = owned_story_with_role(app, admin, username="bob", role="editor")
    editor = signed_in(app, "bob")

    response = editor.patch(f"/stories/{story_id}", json={"name": "Brass Meridian"})

    assert response.status_code == 200
    assert editor.get(f"/stories/{story_id}").get_json()["name"] == "Brass Meridian"


def test_owner_can_rename_a_story(app, admin):
    story_id = owned_story_with_role(app, admin, username="bob", role=None)
    owner = app.test_client()
    owner.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )

    response = owner.patch(f"/stories/{story_id}", json={"name": "Brass Meridian"})

    assert response.status_code == 200
    source = json.loads(source_path(app, admin["id"], story_id).read_text())
    assert source["name"] == "Brass Meridian"
    assert source["passages"] == NEW_STORY["passages"]


def test_viewer_cannot_rename_a_story(app, admin):
    story_id = owned_story_with_role(app, admin, username="bob", role="viewer")
    viewer = signed_in(app, "bob")

    response = viewer.patch(f"/stories/{story_id}", json={"name": "Stolen"})

    assert response.status_code == 403
    assert viewer.get(f"/stories/{story_id}").get_json()["name"] == NEW_STORY["name"]


def test_stranger_cannot_rename_a_story(app, admin):
    story_id = owned_story_with_role(app, admin, username="bob", role=None)
    stranger = signed_in(app, "bob")

    response = stranger.patch(f"/stories/{story_id}", json={"name": "Stolen"})

    assert response.status_code in (403, 404)
