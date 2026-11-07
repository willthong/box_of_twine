"""A story may have one revocable public link.

Seams:
  POST   /stories/<id>/public-link
  GET    /stories/<id>/public-link
  DELETE /stories/<id>/public-link
  GET    /public/<slug>
"""

from box_of_twine.users import create_user

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "passages": [{"name": "Start", "text": "You wake in a garden of brass."}],
}


def signed_in(app, username, password=None):
    client = app.test_client()
    response = client.post(
        "/login",
        data={
            "username": username,
            "password": password or f"{username}-password",
        },
    )
    assert response.status_code == 302
    return client


def owner_fixture(app, admin):
    return signed_in(app, admin["username"], admin["password"])


def make_story(app, admin):
    owner = owner_fixture(app, admin)
    response = owner.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    return owner, response.get_json()["id"]


def make_user(app, username):
    with app.app_context():
        return create_user(username, f"{username}-password")


def test_owner_creates_and_reads_a_public_link(app, admin):
    owner, story_id = make_story(app, admin)

    created = owner.post(f"/stories/{story_id}/public-link")
    assert created.status_code == 201
    slug = created.get_json()["slug"]
    assert slug

    response = owner.get(f"/stories/{story_id}/public-link")
    assert response.status_code == 200
    assert response.get_json() == {"slug": slug}


def test_creating_a_link_twice_keeps_the_single_existing_link(app, admin):
    owner, story_id = make_story(app, admin)

    first = owner.post(f"/stories/{story_id}/public-link").get_json()["slug"]
    second = owner.post(f"/stories/{story_id}/public-link").get_json()["slug"]

    assert second == first


def test_any_role_can_read_the_link_but_only_an_owner_can_create_or_revoke(
    app, admin
):
    owner, story_id = make_story(app, admin)
    bob_id = make_user(app, "bob")
    owner.post(
        f"/stories/{story_id}/shares", json={"user_id": bob_id, "role": "viewer"}
    )
    slug = owner.post(f"/stories/{story_id}/public-link").get_json()["slug"]

    viewer = signed_in(app, "bob")
    assert viewer.get(f"/stories/{story_id}/public-link").get_json() == {"slug": slug}
    assert viewer.post(f"/stories/{story_id}/public-link").status_code in (403, 404)
    assert viewer.delete(f"/stories/{story_id}/public-link").status_code in (403, 404)

    assert owner.get(f"/stories/{story_id}/public-link").get_json() == {"slug": slug}


def test_no_link_reads_as_none(app, admin):
    owner, story_id = make_story(app, admin)

    response = owner.get(f"/stories/{story_id}/public-link")

    assert response.status_code == 200
    assert response.get_json() == {"slug": None}


def test_revoking_removes_the_link_and_its_public_url(app, admin):
    owner, story_id = make_story(app, admin)
    slug = owner.post(f"/stories/{story_id}/public-link").get_json()["slug"]
    assert app.test_client().get(f"/public/{slug}").status_code == 200

    response = owner.delete(f"/stories/{story_id}/public-link")
    assert response.status_code == 204

    assert owner.get(f"/stories/{story_id}/public-link").get_json() == {"slug": None}
    assert app.test_client().get(f"/public/{slug}").status_code == 404


def test_public_url_is_anonymous_and_compiles_the_latest_story(app, admin):
    owner, story_id = make_story(app, admin)
    slug = owner.post(f"/stories/{story_id}/public-link").get_json()["slug"]

    response = app.test_client().get(f"/public/{slug}")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"The Clockwork Garden" in response.data
    assert NEW_STORY["passages"][0]["text"].encode() in response.data

    edited = {**NEW_STORY, "name": "Brass Meridian"}
    assert owner.put(f"/stories/{story_id}", json=edited).status_code == 200

    response = app.test_client().get(f"/public/{slug}")
    assert b"Brass Meridian" in response.data


def test_deleting_the_story_removes_its_public_link(app, admin):
    owner, story_id = make_story(app, admin)
    slug = owner.post(f"/stories/{story_id}/public-link").get_json()["slug"]

    assert owner.delete(f"/stories/{story_id}").status_code == 204

    assert app.test_client().get(f"/public/{slug}").status_code == 404
