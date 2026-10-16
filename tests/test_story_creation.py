"""Slice 3 — create a story from the home form. Seam: `POST /stories/new`.

The home page offers a "New story" form that posts a ``name``. Submitting it
must mint a fresh, empty Harlowe story (a ``Start`` passage and an ifid),
persist it like any other story, and drop the owner straight into the editor
for it. Anonymous visitors are sent to log in and nothing is created.
"""

import json
import re
from pathlib import Path

from box_of_twine.db import get_db

# A Twine ifid is an uppercase UUID. This is the Twine convention, not a
# restatement of how the app happens to generate one.
IFID = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}")


def login_as(client, user):
    return client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )


def source_path(app, user_id, story_id):
    return (
        Path(app.config["DATA_DIR"])
        / "users"
        / str(user_id)
        / "stories"
        / f"{story_id}.json"
    )


def story_id_from(response):
    match = re.fullmatch(r"/edit/(\d+)", response.headers["Location"])
    assert match, (
        f"expected a redirect into the editor, got {response.headers['Location']!r}"
    )
    return int(match.group(1))


def test_form_post_creates_a_valid_harlowe_story_and_redirects_to_the_editor(
    app, client, admin
):
    login_as(client, admin)

    response = client.post("/stories/new", data={"name": "Brass Meridian"})

    assert response.status_code == 303
    story_id = story_id_from(response)

    source = source_path(app, admin["id"], story_id)
    assert source.exists(), "the story source file must be written"
    story = json.loads(source.read_text())
    assert story["name"] == "Brass Meridian"
    assert story["format"] == "Harlowe"
    assert story["start"] == "Start"
    assert "Start" in [passage["name"] for passage in story["passages"]]
    assert IFID.fullmatch(story["ifid"]), story["ifid"]

    with app.app_context():
        row = (
            get_db()
            .execute("SELECT owner_id, name FROM stories WHERE id = ?", (story_id,))
            .fetchone()
        )
    assert row is not None, "the story metadata row must be written"
    assert row["owner_id"] == admin["id"]
    assert row["name"] == "Brass Meridian"


def test_a_story_created_from_the_form_appears_on_the_home_page(app, client, admin):
    login_as(client, admin)
    created = client.post("/stories/new", data={"name": "Brass Meridian"})
    assert created.status_code == 303
    story_id = story_id_from(created)

    response = client.get("/")

    assert response.status_code == 200
    assert f"/edit/{story_id}".encode() in response.data
    assert b"Brass Meridian" in response.data


def test_anonymous_form_post_redirects_to_login_and_creates_nothing(app, client):
    response = client.post("/stories/new", data={"name": "Sneaky"})

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")

    with app.app_context():
        count = get_db().execute("SELECT COUNT(*) FROM stories").fetchone()[0]
    assert count == 0

    users_dir = Path(app.config["DATA_DIR"]) / "users"
    assert list(users_dir.rglob("*.json")) == []
