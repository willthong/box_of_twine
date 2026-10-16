"""The editor is wired to server-side story storage, not browser storage.

Twine's own editor persists stories in browser localStorage under a private
schema (`twine-stories`, `twine-passages`, ...). Box of Twine keeps the
canonical story on disk in the story-format JSON shape. These tests pin the
conversion between the two shapes and the routes that serve and save a story
from the server.
"""

import json
from pathlib import Path

from box_of_twine.editor import canonical_to_internal, internal_to_canonical


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


SOURCE = {
    "name": "The Clockwork Garden",
    "ifid": "6E1C0F2A-5D4B-4C3A-9F8E-1A2B3C4D5E6F",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "start": "Gate",
    "passages": [
        {"name": "Start", "text": "You wake in a garden of brass."},
        {"name": "Gate", "text": "A gate hums with clockwork."},
    ],
}


def test_canonical_to_internal_maps_a_story_into_twine_local_storage_records():
    internal = canonical_to_internal(SOURCE, story_id=7)

    story = internal["story"]
    assert story["id"] == "7"
    assert story["name"] == "The Clockwork Garden"
    assert story["ifid"] == SOURCE["ifid"]
    assert story["storyFormat"] == "Harlowe"
    assert story["storyFormatVersion"] == "3.3.9"
    assert story["stylesheet"] == ""
    assert story["script"] == ""
    assert story["tags"] == []

    passages = {passage["name"]: passage for passage in internal["passages"]}
    assert set(passages) == {"Start", "Gate"}
    assert passages["Start"]["text"] == "You wake in a garden of brass."
    assert passages["Gate"]["text"] == "A gate hums with clockwork."
    assert story["startPassage"] == passages["Gate"]["id"]

    for passage in internal["passages"]:
        assert passage["story"] == "7"
        assert passage["tags"] == []
        assert passage["left"] == 0
        assert passage["top"] == 0
        assert passage["width"] == 100
        assert passage["height"] == 100


def test_internal_to_canonical_rebuilds_the_disk_story_shape():
    internal = canonical_to_internal(SOURCE, story_id=7)
    story = internal["story"]
    gate = next(p for p in internal["passages"] if p["name"] == "Gate")
    start = next(p for p in internal["passages"] if p["name"] == "Start")

    story["startPassage"] = gate["id"]
    start["tags"] = ["begin"]
    story["stylesheet"] = "body { background: brass; }"
    story["script"] = "window.clockwork = true;"
    story["tags"] = ["clockwork"]

    assert internal_to_canonical(internal) == {
        "name": "The Clockwork Garden",
        "ifid": SOURCE["ifid"],
        "format": "Harlowe",
        "formatVersion": "3.3.9",
        "start": "Gate",
        "passages": [
            {"name": "Start", "text": "You wake in a garden of brass.", "tags": ["begin"]},
            {"name": "Gate", "text": "A gate hums with clockwork."},
        ],
        "tags": ["clockwork"],
        "stylesheet": "body { background: brass; }",
        "script": "window.clockwork = true;",
    }


def test_editor_shell_embeds_the_server_story_and_a_bootstrap(app, client, admin):
    login_as(client, admin)
    created = client.post("/stories", json=SOURCE)
    story_id = created.get_json()["id"]

    response = client.get(f"/edit/{story_id}")

    assert response.status_code == 200
    assert b'id="box-of-twine-editor-data"' in response.data
    assert b'id="box-of-twine-editor-bootstrap"' in response.data

    payload = json.loads(
        response.data.split(b'id="box-of-twine-editor-data">')[1].split(b"</script>")[0]
    )
    assert payload["storyId"] == str(story_id)
    assert payload["story"]["name"] == "The Clockwork Garden"
    assert {p["name"] for p in payload["passages"]} == {"Start", "Gate"}


def test_editor_save_persists_twine_internal_records_as_the_disk_story(
    app, client, admin
):
    login_as(client, admin)
    created = client.post("/stories", json=SOURCE)
    story_id = created.get_json()["id"]

    internal = canonical_to_internal(SOURCE, story_id=story_id)
    internal["story"]["name"] = "Brass Meridian"

    response = client.put(f"/stories/{story_id}/editor", json=internal)
    assert response.status_code == 200

    saved = json.loads(story_source_path(app, admin["id"], story_id).read_text())
    assert saved["name"] == "Brass Meridian"
    assert saved["start"] == "Gate"
    assert saved["format"] == "Harlowe"
    assert {p["name"] for p in saved["passages"]} == {"Start", "Gate"}

    response = client.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Brass Meridian"


def test_story_path_serves_the_editor_shell_for_browser_navigation(
    app, client, admin
):
    login_as(client, admin)
    created = client.post("/stories", json=SOURCE)
    story_id = created.get_json()["id"]

    response = client.get(
        f"/stories/{story_id}", headers={"Accept": "text/html"}
    )

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b'<div id="root">' in response.data
    assert b'id="box-of-twine-editor-data"' in response.data

    # Without an HTML preference the JSON API is unchanged.
    response = client.get(f"/stories/{story_id}")
    assert response.status_code == 200
    assert response.get_json()["name"] == "The Clockwork Garden"
