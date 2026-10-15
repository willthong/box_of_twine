"""Edit-lock behavior at the HTTP seams.

Acquire/renew:  POST   /stories/<story_id>/lock
Release/break:  DELETE /stories/<story_id>/lock

A story's lock is a per-story lease held by the one user currently editing it.
Writes (PUT) by anyone else are refused with 409 while the lease is live. The
holder, an owner, or an admin may release or force-break it; a peer editor may
not. Reads are never blocked. The production lease is ~10 minutes; the lapse
and renewal tests shorten it through ``LOCK_LEASE_SECONDS`` to avoid waiting.
"""

import time

import pytest

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

LEASE_SECONDS = 0.4
DEFAULT_LEASE_SECONDS = 600


def password_for(username):
    return f"{username}-password"


def login_as(client, user):
    return client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )


def make_user(app, username):
    password = password_for(username)
    with app.app_context():
        user_id = create_user(username, password)
    return {"username": username, "password": password, "id": user_id}


def signed_in(app, user):
    client = app.test_client()
    login_as(client, user)
    return client


def create_story(owner_client):
    response = owner_client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    return response.get_json()["id"]


def grant(owner_client, story_id, user, role):
    response = owner_client.post(
        f"/stories/{story_id}/shares",
        json={"user_id": user["id"], "role": role},
    )
    assert response.status_code == 201


def editors_with_story(app, admin):
    """An admin-owned story shared with bob and carol as editors."""
    bob = make_user(app, "bob")
    carol = make_user(app, "carol")
    owner = signed_in(app, admin)
    story_id = create_story(owner)
    grant(owner, story_id, bob, "editor")
    grant(owner, story_id, carol, "editor")
    return story_id, owner, signed_in(app, bob), signed_in(app, carol)


@pytest.fixture
def short_lease(app):
    app.config["LOCK_LEASE_SECONDS"] = LEASE_SECONDS
    return app


def test_lock_lease_defaults_to_ten_minutes(app):
    assert app.config.get("LOCK_LEASE_SECONDS") == DEFAULT_LEASE_SECONDS


def test_second_editor_is_blocked_while_the_first_holds_the_lock(app, admin):
    story_id, _owner, first, second = editors_with_story(app, admin)

    response = first.post(f"/stories/{story_id}/lock")
    assert response.status_code == 200

    # The second editor cannot take the lease, and is told who holds it.
    response = second.post(f"/stories/{story_id}/lock")
    assert response.status_code == 409
    assert response.get_json()["holder"] == "bob"

    # The server enforces the lock on the write itself, not just on /lock.
    response = second.put(
        f"/stories/{story_id}", json={**NEW_STORY, "name": "Carol's Draft"}
    )
    assert response.status_code == 409

    response = first.put(
        f"/stories/{story_id}", json={**NEW_STORY, "name": "Bob's Draft"}
    )
    assert response.status_code == 200


def test_owner_can_force_break_then_the_second_editor_can_write(app, admin):
    story_id, owner, first, second = editors_with_story(app, admin)
    assert first.post(f"/stories/{story_id}/lock").status_code == 200

    # A peer editor cannot break someone else's lock...
    assert second.delete(f"/stories/{story_id}/lock").status_code == 403

    # ...but an owner can.
    assert owner.delete(f"/stories/{story_id}/lock").status_code == 204

    # The lock is now free, so the second editor's write goes through.
    assert second.post(f"/stories/{story_id}/lock").status_code == 200
    response = second.put(
        f"/stories/{story_id}", json={**NEW_STORY, "name": "Carol's Draft"}
    )
    assert response.status_code == 200


def test_admin_can_force_break_a_lock_on_a_story_they_do_not_own(app, admin):
    bob = make_user(app, "bob")
    carol = make_user(app, "carol")
    owner = signed_in(app, bob)
    story_id = create_story(owner)
    grant(owner, story_id, carol, "editor")
    assert owner.post(f"/stories/{story_id}/lock").status_code == 200

    admin_client = signed_in(app, admin)
    assert admin_client.delete(f"/stories/{story_id}/lock").status_code == 204

    editor = signed_in(app, carol)
    assert editor.post(f"/stories/{story_id}/lock").status_code == 200


def test_holder_releasing_the_lock_lets_another_editor_write(app, admin):
    story_id, _owner, first, second = editors_with_story(app, admin)
    assert first.post(f"/stories/{story_id}/lock").status_code == 200

    assert first.delete(f"/stories/{story_id}/lock").status_code == 204

    assert second.post(f"/stories/{story_id}/lock").status_code == 200
    response = second.put(
        f"/stories/{story_id}", json={**NEW_STORY, "name": "Carol's Draft"}
    )
    assert response.status_code == 200


def test_lock_lapses_when_its_lease_expires(short_lease, admin):
    app = short_lease
    story_id, _owner, first, second = editors_with_story(app, admin)
    assert first.post(f"/stories/{story_id}/lock").status_code == 200

    time.sleep(LEASE_SECONDS + 0.2)

    # The lapsed lease is no longer held, so the second editor may take it.
    assert second.post(f"/stories/{story_id}/lock").status_code == 200


def test_activity_renews_the_lease(short_lease, admin):
    app = short_lease
    story_id, _owner, first, second = editors_with_story(app, admin)
    assert first.post(f"/stories/{story_id}/lock").status_code == 200

    # A write before the lease lapses keeps it alive...
    time.sleep(LEASE_SECONDS * 0.6)
    response = first.put(
        f"/stories/{story_id}", json={**NEW_STORY, "name": "Bob's Draft"}
    )
    assert response.status_code == 200

    # ...so after more than the original lease, measured from acquisition but
    # less than a full lease since the write, it is still held.
    time.sleep(LEASE_SECONDS * 0.6)
    assert second.post(f"/stories/{story_id}/lock").status_code == 409


def test_reads_are_never_blocked_by_a_lock(app, admin):
    bob = make_user(app, "bob")
    dave = make_user(app, "dave")
    owner = signed_in(app, admin)
    story_id = create_story(owner)
    grant(owner, story_id, bob, "editor")
    grant(owner, story_id, dave, "viewer")

    holder = signed_in(app, bob)
    assert holder.post(f"/stories/{story_id}/lock").status_code == 200

    reader = signed_in(app, dave)
    response = reader.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == NEW_STORY


def test_locks_are_per_story(app, admin):
    bob = make_user(app, "bob")
    carol = make_user(app, "carol")
    owner = signed_in(app, admin)
    first_story = create_story(owner)
    second_story = create_story(owner)
    for story_id in (first_story, second_story):
        grant(owner, story_id, bob, "editor")
        grant(owner, story_id, carol, "editor")

    bob_client = signed_in(app, bob)
    carol_client = signed_in(app, carol)
    assert bob_client.post(f"/stories/{first_story}/lock").status_code == 200

    # A different story is locked independently...
    assert carol_client.post(f"/stories/{second_story}/lock").status_code == 200
    response = carol_client.put(
        f"/stories/{second_story}", json={**NEW_STORY, "name": "Second"}
    )
    assert response.status_code == 200

    # ...and Bob's lock does not cover the first story's sibling.
    response = carol_client.put(
        f"/stories/{first_story}", json={**NEW_STORY, "name": "First"}
    )
    assert response.status_code == 409
