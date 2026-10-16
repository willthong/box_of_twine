"""SQLite metadata must live on the data volume (v1.1 Slice 1).

These exercise `create_app` config directly rather than the shared `app`
fixture, which always supplies `DATABASE` explicitly.
"""

import uuid

from box_of_twine import create_app
from box_of_twine.users import create_user

DATABASE_FILENAME = "box_of_twine.sqlite"

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "passages": [
        {"name": "Start", "text": "You wake in a garden of brass."},
    ],
}


def make_app(data_dir, **config):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATA_DIR": str(data_dir),
            **config,
        }
    )


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def test_default_database_is_derived_from_the_data_dir(tmp_path):
    data_dir = tmp_path / "data"

    app = make_app(data_dir)

    assert app.config["DATABASE"] == str(data_dir / DATABASE_FILENAME)


def test_explicit_database_wins_over_the_derived_default(tmp_path):
    data_dir = tmp_path / "data"
    explicit = tmp_path / "elsewhere.sqlite"

    app = make_app(data_dir, DATABASE=str(explicit))

    assert app.config["DATABASE"] == str(explicit)
    assert explicit.exists()


def test_recreating_the_app_on_the_same_data_dir_keeps_users_and_stories(tmp_path):
    data_dir = tmp_path / "data"
    # Unique so the test stays honest while the default still falls back to a
    # shared database across runs.
    username = f"bob-{uuid.uuid4().hex}"
    password = "bob-password"

    first = make_app(data_dir)
    with first.app_context():
        create_user(username, password)
    client = first.test_client()
    assert login(client, username, password).status_code == 302
    response = client.post("/stories", json=NEW_STORY)
    assert response.status_code == 201
    story_id = response.get_json()["id"]

    # A restart against the same volume still knows the user and their story.
    restarted = make_app(data_dir)
    client = restarted.test_client()
    assert login(client, username, password).status_code == 302
    response = client.get("/stories")
    assert response.status_code == 200
    assert story_id in [story["id"] for story in response.get_json()]

    # A different volume starts empty: the database is per data volume.
    other_volume = make_app(tmp_path / "other-data")
    client = other_volume.test_client()
    assert login(client, username, password).status_code == 401
