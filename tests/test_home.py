"""Slice 2 — home page. Seam: `GET /`.

Rendering contract these tests pin down: an anonymous visitor is sent to the
login page; an authenticated user gets an HTML index of every story they can
reach — the ones they own and the ones shared with them — each linking into the
editor, alongside their own username and a form for starting a new story.
"""

from html.parser import HTMLParser
from typing import TypedDict

import pytest

from box_of_twine.users import create_user

NEW_STORY = {
    "name": "Untitled",
    "start": "Start",
    "format": "Harlowe",
    "passages": [{"name": "Start", "text": "Once upon a time."}],
}


def login_as(client, user):
    return client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )


def create_story(client, name):
    response = client.post("/stories", json={**NEW_STORY, "name": name})
    assert response.status_code == 201
    return response.get_json()["id"]


class _Form(TypedDict):
    action: str | None
    method: str
    inputs: dict[str, str | None]


class _PageParser(HTMLParser):
    """Collect the anchors and forms a rendered page exposes."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.forms: list[_Form] = []
        self._link = None
        self._form: _Form | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self._link = (attrs.get("href", ""), [])
        elif tag == "form":
            self._form = {
                "action": attrs.get("action", ""),
                "method": (attrs.get("method") or "get").lower(),
                "inputs": {},
            }
        elif (
            tag in ("input", "md-outlined-text-field", "md-filled-text-field")
            and self._form is not None
            and attrs.get("name")
        ):
            self._form["inputs"][attrs["name"]] = attrs.get("type", "text")

    def handle_data(self, data):
        if self._link is not None:
            self._link[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self.links.append((self._link[0], "".join(self._link[1]).strip()))
            self._link = None
        elif tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None


def parsed(content: bytes) -> _PageParser:
    page = _PageParser()
    page.feed(content.decode())
    return page


@pytest.fixture
def bob_home(app):
    """A client logged in as bob, who owns one story and has one shared."""
    with app.app_context():
        create_user("alice", "alice-password")
        bob_id = create_user("bob", "bob-password")

    alice = app.test_client()
    login_as(alice, {"username": "alice", "password": "alice-password"})
    shared_id = create_story(alice, "Alice's Clockwork Garden")
    response = alice.post(
        f"/stories/{shared_id}/shares",
        json={"user_id": bob_id, "role": "editor"},
    )
    assert response.status_code == 201

    bob = app.test_client()
    login_as(bob, {"username": "bob", "password": "bob-password"})
    owned_id = create_story(bob, "Bob's Brass Meridian")

    return bob, owned_id, shared_id


def test_anonymous_home_redirects_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_home_lists_owned_and_shared_stories_with_editor_links(bob_home):
    bob, owned_id, shared_id = bob_home

    response = bob.get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    links = parsed(response.data).links
    assert (f"/edit/{owned_id}", "Bob's Brass Meridian") in links
    assert (f"/edit/{shared_id}", "Alice's Clockwork Garden") in links


def test_home_shows_the_username_and_a_new_story_form(bob_home):
    bob, _, _ = bob_home

    response = bob.get("/")

    assert response.status_code == 200
    assert b"bob" in response.data
    forms = parsed(response.data).forms
    assert any(
        form["action"] == "/stories/new"
        and form["method"] == "post"
        and "name" in form["inputs"]
        for form in forms
    ), forms
