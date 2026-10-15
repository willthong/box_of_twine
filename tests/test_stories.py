import json
import re
from pathlib import Path

from box_of_twine.db import get_db
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


def story_source_path(app, user_id, story_id):
    return (
        Path(app.config["DATA_DIR"])
        / "users"
        / str(user_id)
        / "stories"
        / f"{story_id}.json"
    )


def listed_story_ids(response):
    return [story["id"] for story in response.get_json()]


def test_creating_story_writes_source_and_lists_it_only_for_owner(app, client, admin):
    with app.app_context():
        create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)

    assert response.status_code == 201
    story_id = response.get_json()["id"]

    source = story_source_path(app, admin["id"], story_id)
    assert source.exists()
    saved = json.loads(source.read_text())
    assert saved["name"] == NEW_STORY["name"]
    assert saved["passages"] == NEW_STORY["passages"]

    response = client.get("/stories")
    assert response.status_code == 200
    assert story_id in listed_story_ids(response)

    other = app.test_client()
    login_as(other, {"username": "bob", "password": "bob-password"})
    response = other.get("/stories")
    assert response.status_code == 200
    assert story_id not in listed_story_ids(response)


def test_editor_serves_the_twine_shell_for_a_story(app, client, admin):
    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    response = client.get(f"/edit/{story_id}")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b'<div id="root">' in response.data
    # Relative asset and runtime story-format URLs must resolve under the
    # Flask static mount, either via an injected <base> or absolute URLs.
    assert (
        re.search(rb'<base\b[^>]*href="/static/twine/"', response.data)
        or b"/static/twine/assets/" in response.data
    ), "the editor shell must load its assets from /static/twine/"


def test_story_json_is_returned_to_its_owner(app, client, admin):
    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    response = client.get(f"/stories/{story_id}")

    assert response.status_code == 200
    assert response.get_json() == NEW_STORY


def test_story_json_is_hidden_from_a_non_owner(app, client, admin):
    with app.app_context():
        create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    other = app.test_client()
    login_as(other, {"username": "bob", "password": "bob-password"})
    response = other.get(f"/stories/{story_id}")

    assert response.status_code in (403, 404)


def test_saving_story_round_trips_passages_and_metadata(app, client, admin):
    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    response = client.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == NEW_STORY

    edited = {
        "name": "The Clockwork Garden",
        "start": "Cellar",
        "format": "Harlowe",
        "formatVersion": "3.3.9",
        "ifid": "6E1C0F2A-5D4B-4C3A-9F8E-1A2B3C4D5E6F",
        "tags": ["clockwork"],
        "stylesheet": "body { background: brass; }",
        "script": "window.clockwork = true;",
        "passages": [
            {"name": "Start", "text": "You wake in a garden of brass."},
            {"name": "Gate", "text": "A gate hums with clockwork."},
            {"name": "Cellar", "text": "Below, gears turn."},
        ],
    }

    response = client.put(f"/stories/{story_id}", json=edited)
    assert response.status_code == 200

    response = client.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == edited


def test_saving_story_is_denied_to_a_non_owner(app, client, admin):
    with app.app_context():
        create_user("bob", "bob-password")

    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    other = app.test_client()
    login_as(other, {"username": "bob", "password": "bob-password"})
    response = other.put(f"/stories/{story_id}", json={**NEW_STORY, "name": "Stolen"})
    assert response.status_code in (403, 404)

    response = client.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json() == NEW_STORY


def test_renaming_story_updates_the_source_and_the_listing(app, client, admin):
    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)

    assert response.status_code == 201
    story_id = response.get_json()["id"]

    response = client.patch(f"/stories/{story_id}", json={"name": "Brass Meridian"})
    assert response.status_code == 200

    source = story_source_path(app, admin["id"], story_id)
    renamed = json.loads(source.read_text())
    assert renamed["name"] == "Brass Meridian"
    assert renamed["passages"] == NEW_STORY["passages"]

    response = client.get("/stories")
    assert response.status_code == 200
    names = {story["id"]: story["name"] for story in response.get_json()}
    assert names[story_id] == "Brass Meridian"


def test_deleting_story_removes_source_and_cascades_shares_and_publications(
    app, client, admin
):
    login_as(client, admin)
    response = client.post("/stories", json=NEW_STORY)

    assert response.status_code == 201
    story_id = response.get_json()["id"]
    source = story_source_path(app, admin["id"], story_id)
    assert source.exists()

    with app.app_context():
        db = get_db()
        tables = {
            row["name"]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"shares", "publications"} <= tables, (
            "deleting a story must cascade the shares and publications metadata tables"
        )
        db.execute(
            "INSERT INTO shares (story_id, user_id, role) VALUES (?, ?, ?)",
            (story_id, admin["id"], "viewer"),
        )
        db.execute(
            "INSERT INTO publications (story_id, slug, visibility) VALUES (?, ?, ?)",
            (story_id, "brass-meridian", "public"),
        )
        db.commit()

    response = client.delete(f"/stories/{story_id}")
    assert response.status_code == 204

    assert not source.exists()
    assert story_id not in listed_story_ids(client.get("/stories"))

    with app.app_context():
        db = get_db()
        shares = db.execute(
            "SELECT COUNT(*) FROM shares WHERE story_id = ?", (story_id,)
        ).fetchone()[0]
        publications = db.execute(
            "SELECT COUNT(*) FROM publications WHERE story_id = ?", (story_id,)
        ).fetchone()[0]
    assert shares == 0
    assert publications == 0
