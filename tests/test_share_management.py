"""Story sharing management through the browser's JSON seams.

Seams:
  GET    /users
  POST   /stories/<id>/shares
  GET    /stories/<id>/shares
  DELETE /stories/<id>/shares/<user_id>
"""

from box_of_twine.users import create_user

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "passages": [{"name": "Start", "text": "You wake in a garden of brass."}],
}


def make_user(app, username, *, disabled=False):
    with app.app_context():
        user_id = create_user(username, f"{username}-password")
        if disabled:
            from box_of_twine.users import set_disabled

            set_disabled(user_id, True)
    return user_id


def signed_in(app, username):
    client = app.test_client()
    response = client.post(
        "/login", data={"username": username, "password": f"{username}-password"}
    )
    assert response.status_code == 302
    return client


def owner_story(app, admin, name="The Clockwork Garden"):
    client = app.test_client()
    client.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )
    response = client.post("/stories", json={**NEW_STORY, "name": name})
    assert response.status_code == 201
    return client, response.get_json()["id"]


def test_users_endpoint_lists_every_user_with_disabled_state(app, admin):
    bob_id = make_user(app, "bob")
    dana_id = make_user(app, "dana", disabled=True)

    response = signed_in(app, "bob").get("/users")

    assert response.status_code == 200
    users = {user["id"]: user for user in response.get_json()}
    assert users[bob_id]["username"] == "bob"
    assert users[bob_id]["disabled"] is False
    assert users[dana_id]["disabled"] is True
    assert admin["id"] in users


def test_users_endpoint_requires_authentication(app):
    response = app.test_client().get("/users")

    assert response.status_code == 401


def test_sharing_twice_upserts_the_role_instead_of_duplicating(app, admin):
    owner, story_id = owner_story(app, admin)
    bob_id = make_user(app, "bob")

    first = owner.post(
        f"/stories/{story_id}/shares", json={"user_id": bob_id, "role": "viewer"}
    )
    assert first.status_code == 201
    second = owner.post(
        f"/stories/{story_id}/shares", json={"user_id": bob_id, "role": "editor"}
    )
    assert second.status_code == 201

    response = owner.get(f"/stories/{story_id}/shares")
    assert response.status_code == 200
    assert response.get_json() == [
        {"user_id": bob_id, "username": "bob", "role": "editor"}
    ]


def test_owner_lists_shares_and_can_revoke_one(app, admin):
    owner, story_id = owner_story(app, admin)
    bob_id = make_user(app, "bob")
    carol_id = make_user(app, "carol")
    owner.post(
        f"/stories/{story_id}/shares", json={"user_id": bob_id, "role": "viewer"}
    )
    owner.post(
        f"/stories/{story_id}/shares", json={"user_id": carol_id, "role": "editor"}
    )

    response = owner.get(f"/stories/{story_id}/shares")
    assert {(s["username"], s["role"]) for s in response.get_json()} == {
        ("bob", "viewer"),
        ("carol", "editor"),
    }

    response = owner.delete(f"/stories/{story_id}/shares/{bob_id}")
    assert response.status_code == 204
    response = owner.get(f"/stories/{story_id}/shares")
    assert response.get_json() == [
        {"user_id": carol_id, "username": "carol", "role": "editor"}
    ]


def test_only_an_owner_can_list_grant_or_revoke_shares(app, admin):
    owner, story_id = owner_story(app, admin)
    bob_id = make_user(app, "bob")
    carol_id = make_user(app, "carol")
    owner.post(
        f"/stories/{story_id}/shares", json={"user_id": bob_id, "role": "editor"}
    )
    editor = signed_in(app, "bob")

    assert editor.get(f"/stories/{story_id}/shares").status_code in (403, 404)
    assert (
        editor.post(
            f"/stories/{story_id}/shares",
            json={"user_id": carol_id, "role": "viewer"},
        ).status_code
        in (403, 404)
    )
    assert editor.delete(f"/stories/{story_id}/shares/{bob_id}").status_code in (
        403,
        404,
    )

    # The refused grant really did not happen.
    assert (
        owner.post(
            f"/stories/{story_id}/shares",
            json={"user_id": carol_id, "role": "viewer"},
        ).status_code
        == 201
    )
