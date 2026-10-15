from box_of_twine.users import create_user

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
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


def share(client, story_id, user_id, role):
    return client.post(
        f"/stories/{story_id}/shares", json={"user_id": user_id, "role": role}
    )


def owned_story_shared_with(app, client, admin, *, username, role):
    """Create a story as admin and grant *username* the given role on it."""
    with app.app_context():
        user_id = create_user(username, f"{username}-password")

    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    response = share(client, story_id, user_id, role)
    assert response.status_code == 201

    return story_id, user_id


def test_editor_can_save_the_story(app, client, admin):
    story_id, _ = owned_story_shared_with(
        app, client, admin, username="bob", role="editor"
    )

    editor = app.test_client()
    login_as(editor, {"username": "bob", "password": "bob-password"})

    edited = {**NEW_STORY, "name": "Brass Meridian"}
    response = editor.put(f"/stories/{story_id}", json=edited)
    assert response.status_code == 200

    response = editor.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Brass Meridian"


def test_owner_can_share_the_story_with_another_user(app, client, admin):
    story_id, _ = owned_story_shared_with(
        app, client, admin, username="bob", role="owner"
    )
    with app.app_context():
        carol_id = create_user("carol", "carol-password")

    owner = app.test_client()
    login_as(owner, {"username": "bob", "password": "bob-password"})

    response = share(owner, story_id, carol_id, "viewer")
    assert response.status_code == 201

    # The new share is only real if the recipient can read the story.
    carol = app.test_client()
    login_as(carol, {"username": "carol", "password": "carol-password"})
    response = carol.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == NEW_STORY


def test_owner_can_delete_the_story(app, client, admin):
    story_id, _ = owned_story_shared_with(
        app, client, admin, username="bob", role="owner"
    )

    owner = app.test_client()
    login_as(owner, {"username": "bob", "password": "bob-password"})

    response = owner.delete(f"/stories/{story_id}")
    assert response.status_code == 204

    response = client.get(f"/stories/{story_id}")
    assert response.status_code == 404


def test_owner_can_grant_owner_to_another_user(app, client, admin):
    story_id, _ = owned_story_shared_with(
        app, client, admin, username="bob", role="owner"
    )
    with app.app_context():
        carol_id = create_user("carol", "carol-password")

    owner = app.test_client()
    login_as(owner, {"username": "bob", "password": "bob-password"})

    # "transfer" is just granting owner; owners remain co-equal.
    response = share(owner, story_id, carol_id, "owner")
    assert response.status_code == 201

    # The new owner has full control and can share onward.
    with app.app_context():
        dave_id = create_user("dave", "dave-password")
    successor = app.test_client()
    login_as(successor, {"username": "carol", "password": "carol-password"})
    response = share(successor, story_id, dave_id, "viewer")
    assert response.status_code == 201

    dave = app.test_client()
    login_as(dave, {"username": "dave", "password": "dave-password"})
    response = dave.get(f"/stories/{story_id}")
    assert response.status_code == 200


def test_owner_shares_story_with_viewer_who_can_read_but_not_write(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    response = client.post(
        f"/stories/{story_id}/shares",
        json={"user_id": bob_id, "role": "viewer"},
    )
    assert response.status_code == 201

    viewer = app.test_client()
    login_as(viewer, {"username": "bob", "password": "bob-password"})

    response = viewer.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == NEW_STORY

    response = viewer.put(f"/stories/{story_id}", json={**NEW_STORY, "name": "Stolen"})
    assert response.status_code == 403


def test_viewer_and_editor_can_open_the_editor(app, client, admin):
    with app.app_context():
        bob_id = create_user("bob", "bob-password")
        carol_id = create_user("carol", "carol-password")

    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    assert share(client, story_id, bob_id, "viewer").status_code == 201
    assert share(client, story_id, carol_id, "editor").status_code == 201

    for username, role in (("bob", "viewer"), ("carol", "editor")):
        reader = app.test_client()
        login_as(reader, {"username": username, "password": f"{username}-password"})
        response = reader.get(f"/edit/{story_id}")
        assert response.status_code == 200, f"{role} must be able to open the editor"
        assert response.mimetype == "text/html"
