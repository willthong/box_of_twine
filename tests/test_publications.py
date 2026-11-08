"""Publish behavior at the HTTP seams.

Create a publication:  POST /stories/<story_id>/publications
Read a publication:    GET  /p/<slug>

A publication is an immutable compiled HTML artifact of a story with a
visibility (private/shared/public) and a stable URL. Compilation happens
server-side in Python by substituting the story into the story format's
``{{STORY_NAME}}``/``{{STORY_DATA}}`` placeholders (ADR 0002). Only an owner
may create or manage publications; a public publication is reachable by
anyone with the URL, a private one only by the story's owner, and a shared
one by the story's named users.
"""

from html.parser import HTMLParser
from typing import Any

from box_of_twine.users import create_user

NEW_STORY: dict[str, Any] = {
    "name": "The Clockwork Garden",
    "start": "Start",
    "format": "Harlowe",
    "formatVersion": "3.3.9",
    "passages": [
        {"name": "Start", "text": "You wake in a garden of brass."},
        {"name": "Gate", "text": "A gate hums with clockwork."},
    ],
}


class _StoryDataParser(HTMLParser):
    """Collect the story-data element and its passages from compiled HTML."""

    story: dict[str, Any] | None
    passages: list[dict[str, Any]]
    _passage: dict[str, Any] | None

    def __init__(self):
        super().__init__()
        self.story = None
        self.passages = []
        self._passage = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "tw-storydata":
            self.story = values
        elif tag == "tw-passagedata":
            self._passage = {"attrs": values, "text": []}

    def handle_data(self, data):
        if self._passage is not None:
            self._passage["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "tw-passagedata" and self._passage is not None:
            self._passage["text"] = "".join(self._passage["text"])
            self.passages.append(self._passage)
            self._passage = None


def compiled_story(html):
    """The story format contract embedded in compiled HTML: Twine story data."""
    parser = _StoryDataParser()
    parser.feed(html.decode())
    assert parser.story is not None, "compiled HTML has no <tw-storydata> element"
    return parser.story, parser.passages


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


def publish(client, story_id, visibility):
    return client.post(
        f"/stories/{story_id}/publications", json={"visibility": visibility}
    )


def share(client, story_id, user_id, role):
    return client.post(
        f"/stories/{story_id}/shares", json={"user_id": user_id, "role": role}
    )


def test_publishing_compiles_standalone_html_containing_the_story_data(
    app, client, admin
):
    login_as(client, admin)
    story_id = create_story(client)

    response = publish(client, story_id, "public")
    assert response.status_code == 201
    slug = response.get_json()["slug"]
    assert isinstance(slug, str) and slug

    response = client.get(f"/p/{slug}")
    assert response.status_code == 200
    assert response.mimetype == "text/html"

    html = response.data
    story, passages = compiled_story(html)
    assert story["name"] == NEW_STORY["name"]
    assert story["format"] == NEW_STORY["format"]
    assert story["format-version"] == NEW_STORY["formatVersion"]
    assert story["startnode"] == "1"
    assert [passage["attrs"]["name"] for passage in passages] == [
        passage["name"] for passage in NEW_STORY["passages"]
    ]
    assert [passage["text"] for passage in passages] == [
        passage["text"] for passage in NEW_STORY["passages"]
    ]
    # The format template was substituted, not served raw.
    assert b"{{STORY_NAME}}" not in html
    assert b"{{STORY_DATA}}" not in html


def test_public_publication_is_reachable_anonymously(app, client, admin):
    login_as(client, admin)
    story_id = create_story(client)

    response = publish(client, story_id, "public")
    assert response.status_code == 201
    slug = response.get_json()["slug"]

    anonymous = app.test_client()
    response = anonymous.get(f"/p/{slug}")
    assert response.status_code == 200
    assert NEW_STORY["passages"][0]["text"].encode() in response.data


def test_private_publication_is_reachable_by_owner_but_denied_to_others(
    app, client, admin
):
    login_as(client, admin)
    story_id = create_story(client)

    response = publish(client, story_id, "private")
    assert response.status_code == 201
    slug = response.get_json()["slug"]

    # The owner can read their own private publication.
    assert client.get(f"/p/{slug}").status_code == 200

    # Another signed-in user cannot.
    bob = make_user(app, "bob")
    other = signed_in(app, bob)
    assert other.get(f"/p/{slug}").status_code in (403, 404)

    # Neither can an anonymous visitor.
    anonymous = app.test_client()
    assert anonymous.get(f"/p/{slug}").status_code in (401, 403, 404)


def test_shared_publication_is_reachable_by_a_named_user_but_not_others(
    app, client, admin
):
    bob = make_user(app, "bob")
    carol = make_user(app, "carol")

    login_as(client, admin)
    story_id = create_story(client)
    assert share(client, story_id, bob["id"], "viewer").status_code == 201

    response = publish(client, story_id, "shared")
    assert response.status_code == 201
    slug = response.get_json()["slug"]

    # The named user can read it.
    assert signed_in(app, bob).get(f"/p/{slug}").status_code == 200
    # An unrelated signed-in user cannot, nor can an anonymous visitor.
    assert signed_in(app, carol).get(f"/p/{slug}").status_code in (403, 404)
    assert app.test_client().get(f"/p/{slug}").status_code in (401, 403, 404)


def test_story_created_from_the_home_form_compiles_when_published(app, client, admin):
    """Regression: a story minted by the home form must be publishable.

    ``POST /stories/new`` builds the source itself, so it has to carry every
    field the compiler reads -- in particular the Harlowe ``formatVersion``.
    """
    login_as(client, admin)

    created = client.post("/stories/new", data={"name": "Brass Meridian"})
    assert created.status_code == 303
    story_id = int(created.headers["Location"].rsplit("/", 1)[-1])

    response = publish(client, story_id, "public")
    assert response.status_code == 201
    slug = response.get_json()["slug"]

    html = client.get(f"/p/{slug}").data
    story, passages = compiled_story(html)
    assert story["name"] == "Brass Meridian"
    assert story["startnode"] == "1"
    assert [(passage["attrs"]["name"], passage["text"]) for passage in passages] == [
        ("Start", "")
    ]
    assert b"{{STORY_DATA}}" not in html


def test_compilation_emits_twine_story_data_with_a_start_node(app, client, admin):
    story = {
        "name": "Brass & Bone",
        "start": "Gate",
        "format": "Harlowe",
        "formatVersion": "3.3.9",
        "passages": [
            {"name": "Start", "text": "A <b>bold</b> opening."},
            {"name": "Gate", "text": 'The gate says "enter".'},
        ],
    }
    login_as(client, admin)
    story_id = client.post("/stories", json=story).get_json()["id"]

    slug = publish(client, story_id, "public").get_json()["slug"]
    html = client.get(f"/p/{slug}").data

    story, passages = compiled_story(html)
    assert story["name"] == "Brass & Bone"
    assert story["startnode"] == "2"
    assert [
        (passage["attrs"]["pid"], passage["attrs"]["name"], passage["text"])
        for passage in passages
    ] == [
        ("1", "Start", "A <b>bold</b> opening."),
        ("2", "Gate", 'The gate says "enter".'),
    ]


def test_only_an_owner_can_create_a_publication(app, client, admin):
    bob = make_user(app, "bob")

    login_as(client, admin)
    story_id = create_story(client)
    assert share(client, story_id, bob["id"], "editor").status_code == 201

    # The owner may publish; the non-owner editor may not.
    assert publish(client, story_id, "public").status_code == 201

    editor = signed_in(app, bob)
    response = publish(editor, story_id, "public")
    assert response.status_code in (403, 404)
