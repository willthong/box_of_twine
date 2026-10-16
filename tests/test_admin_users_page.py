"""Slice 4 — admin users page. Seam: `GET /admin/users`.

Rendering contract these tests pin down: an admin gets an HTML page that lists
every user once, as a list row, showing the username and the user's state —
the row carries the word ``admin`` for an admin and ``disabled`` for a disabled
user. Anonymous visitors are sent to the login page; an authenticated user
without the admin flag is refused with 403.
"""

from html.parser import HTMLParser
from urllib.parse import urlsplit

from box_of_twine.users import create_user

ROW_TAGS = {"li", "tr"}


def login_as(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


class _RowsParser(HTMLParser):
    """Collect each list row's text and the actions of the forms it holds."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row_forms = []
        self._row_tag = None
        self._text = []
        self._forms = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self._row_tag is None and tag in ROW_TAGS:
            self._row_tag = tag
            self._text = []
            self._forms = []
        elif tag == "form" and self._row_tag is not None:
            self._forms.append(attrs.get("action", ""))

    def handle_data(self, data):
        if self._row_tag is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == self._row_tag:
            self.rows.append(" ".join("".join(self._text).split()))
            self.row_forms.append(self._forms)
            self._row_tag = None


def row_for(response, username):
    """The single row listing *username*, lowercased, as a whole word."""
    page = _RowsParser()
    page.feed(response.data.decode())
    matches = [row for row in page.rows if username in row.split()]
    assert matches, f"no row lists {username!r}; rows were {page.rows}"
    return matches[0].lower()


def test_admin_page_lists_every_user_with_admin_and_disabled_state(app, client):
    with app.app_context():
        create_user("ada", "ada-password", is_admin=True)
        create_user("zoe", "zoe-password", is_admin=True)
        dana_id = create_user("dana", "dana-password")
        create_user("erin", "erin-password")

    login_as(client, "ada", "ada-password")
    disabled = client.patch(f"/users/{dana_id}", json={"disabled": True})
    assert disabled.status_code == 200

    response = client.get("/admin/users")

    assert response.status_code == 200
    assert response.mimetype == "text/html"

    # Every user appears exactly once, by name.
    for username in ("ada", "zoe", "dana", "erin"):
        row_for(response, username)

    # The row states whether the user is an admin and whether it is disabled.
    assert "admin" in row_for(response, "zoe")
    assert "disabled" in row_for(response, "dana")
    assert "admin" not in row_for(response, "erin")
    assert "disabled" not in row_for(response, "erin")


def test_admin_page_is_one_listing_of_users_and_their_action_forms(app, client):
    with app.app_context():
        ada_id = create_user("ada", "ada-password", is_admin=True)
        bob_id = create_user("bob", "bob-password")

    login_as(client, "ada", "ada-password")

    response = client.get("/admin/users")

    assert response.status_code == 200
    page = _RowsParser()
    page.feed(response.data.decode())

    # One row per user -- not a summary list plus separate management blocks.
    assert sorted(row.split()[0] for row in page.rows) == ["ada", "bob"]
    # Each row carries that user's update and delete forms.
    assert page.row_forms == [
        [f"/admin/users/{ada_id}/update", f"/admin/users/{ada_id}/delete"],
        [f"/admin/users/{bob_id}/update", f"/admin/users/{bob_id}/delete"],
    ]


def test_anonymous_admin_page_redirects_to_login(client):
    response = client.get("/admin/users")

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/login"


def test_non_admin_admin_page_is_forbidden(app, client):
    with app.app_context():
        create_user("bob", "bob-password")

    login_as(client, "bob", "bob-password")

    response = client.get("/admin/users")

    assert response.status_code == 403
