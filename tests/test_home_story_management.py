"""The home page exposes the story-management menu and dialogs.

Seam: `GET /` plus the static vanilla-JS module it loads.
"""

from html.parser import HTMLParser

from box_of_twine.users import create_user

NEW_STORY = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "passages": [{"name": "Start", "text": "You wake in a garden of brass."}],
}


def signed_in(app, username):
    client = app.test_client()
    response = client.post(
        "/login", data={"username": username, "password": f"{username}-password"}
    )
    assert response.status_code == 302
    return client


class StoryRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = {}
        self._story_id = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag in ("li", "div") and "story-row" in classes:
            self._story_id = attrs.get("data-story-id")
            self.rows[self._story_id] = {
                "attrs": attrs,
                "text": "",
            }
            self._text = []

    def handle_data(self, data):
        if self._story_id is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag in ("li", "div") and self._story_id is not None:
            self.rows[self._story_id]["text"] = " ".join(
                "".join(self._text).split()
            )
            self._story_id = None


def home_rows(html):
    parser = StoryRows()
    parser.feed(html.decode())
    return parser.rows


def make_story_for(app, admin, username, role):
    with app.app_context():
        user_id = create_user(username, f"{username}-password")
    owner = app.test_client()
    owner.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )
    response = owner.post("/stories", json={**NEW_STORY, "name": username})
    assert response.status_code == 201
    story_id = response.get_json()["id"]
    response = owner.post(
        f"/stories/{story_id}/shares", json={"user_id": user_id, "role": role}
    )
    assert response.status_code == 201
    return story_id


def test_home_enriches_each_story_with_role_and_owner(app, admin):
    with app.app_context():
        carol_id = create_user("carol", "carol-password")

    owner = app.test_client()
    owner.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )
    story_id = owner.post("/stories", json=NEW_STORY).get_json()["id"]
    owner.post(
        f"/stories/{story_id}/shares", json={"user_id": carol_id, "role": "viewer"}
    )

    response = owner.get("/")
    row = home_rows(response.data)[str(story_id)]
    assert row["attrs"]["data-story-role"] == "owner"
    assert row["attrs"]["data-story-owner-id"] == str(admin["id"])

    carol = signed_in(app, "carol")
    row = home_rows(carol.get("/").data)[str(story_id)]
    assert row["attrs"]["data-story-role"] == "viewer"
    assert row["attrs"]["data-story-owner-id"] == str(admin["id"])


def test_kebab_menu_offers_actions_for_each_role(app, admin):
    owner_story = make_story_for(app, admin, "owner-user", "owner")
    editor_story = make_story_for(app, admin, "editor-user", "editor")
    viewer_story = make_story_for(app, admin, "viewer-user", "viewer")

    rows = home_rows(signed_in(app, "owner-user").get("/").data)
    assert "Rename" in rows[str(owner_story)]["text"]
    assert "Manage access" in rows[str(owner_story)]["text"]
    assert "Copy public link" in rows[str(owner_story)]["text"]

    rows = home_rows(signed_in(app, "editor-user").get("/").data)
    assert "Rename" in rows[str(editor_story)]["text"]
    assert "Manage access" not in rows[str(editor_story)]["text"]
    assert "Copy public link" in rows[str(editor_story)]["text"]

    rows = home_rows(signed_in(app, "viewer-user").get("/").data)
    assert "Rename" not in rows[str(viewer_story)]["text"]
    assert "Manage access" not in rows[str(viewer_story)]["text"]
    assert "Copy public link" in rows[str(viewer_story)]["text"]


def test_home_loads_the_story_management_module_and_dialogs(app, admin):
    make_story_for(app, admin, "bob", "editor")
    html = signed_in(app, "bob").get("/").data

    assert b"story-management.js" in html
    assert b"<dialog" in html
    assert b'data-current-user-id="' in html
    assert b"\xe2\x8b\xae" in html


def test_story_management_module_calls_the_json_seams(client):
    response = client.get("/static/story-management.js")

    assert response.status_code == 200
    script = response.data
    for seam in (b"/shares", b"/public-link", b"/users", b"PATCH"):
        assert seam in script
