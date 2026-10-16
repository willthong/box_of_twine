"""Logging out: the top-bar user menu and the route that ends the session."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

from box_of_twine.users import create_user


def login_as(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


class _UserMenuParser(HTMLParser):
    """The username shown as a dropdown trigger and the logout form inside it."""

    def __init__(self):
        super().__init__()
        self.details_depth = 0
        self.summaries = []
        self.logout_forms = 0
        self._summary_text = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details":
            self.details_depth += 1
        elif tag == "summary" and self.details_depth:
            self._summary_text = []
        elif (
            tag == "form"
            and self.details_depth
            and attrs.get("action") == "/logout"
            and attrs.get("method", "").lower() == "post"
        ):
            self.logout_forms += 1

    def handle_data(self, data):
        if self._summary_text is not None:
            self._summary_text.append(data)

    def handle_endtag(self, tag):
        if tag == "summary" and self._summary_text is not None:
            self.summaries.append(" ".join("".join(self._summary_text).split()))
            self._summary_text = None
        elif tag == "details":
            self.details_depth -= 1


def user_menu(response):
    page = _UserMenuParser()
    page.feed(response.data.decode())
    return page


def test_posting_logout_ends_the_session_and_redirects_to_login(client, admin):
    login_as(client, admin["username"], admin["password"])
    with client.session_transaction() as session:
        assert session.get("_user_id") == str(admin["id"])

    response = client.post("/logout")

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/login"
    with client.session_transaction() as session:
        assert session.get("_user_id") is None


def test_logout_is_post_only(client, admin):
    login_as(client, admin["username"], admin["password"])

    response = client.get("/logout")

    assert response.status_code == 405


def test_admin_page_offers_a_logout_menu_under_the_username(app, client):
    with app.app_context():
        create_user("ada", "ada-password", is_admin=True)
    login_as(client, "ada", "ada-password")

    menu = user_menu(client.get("/admin/users"))

    assert "ada" in menu.summaries
    assert menu.logout_forms == 1


def test_home_page_offers_a_logout_menu_under_the_username(client, admin):
    login_as(client, admin["username"], admin["password"])

    menu = user_menu(client.get("/"))

    assert admin["username"] in menu.summaries
    assert menu.logout_forms == 1
