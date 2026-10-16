def test_admin_login_sets_session_cookie(client, admin):
    response = client.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )

    assert response.status_code == 302
    assert response.headers.get("Set-Cookie") is not None
    with client.session_transaction() as session:
        assert session.get("_user_id") == str(admin["id"])


def test_admin_login_with_bad_password_returns_401(client, admin):
    response = client.post(
        "/login",
        data={"username": admin["username"], "password": "wrong-password"},
    )

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert session.get("_user_id") is None


def test_successful_login_redirects_to_the_home_page(client, admin):
    response = client.post(
        "/login",
        data={"username": admin["username"], "password": admin["password"]},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    # Following the redirect lands on the authenticated home page.
    assert client.get("/").status_code == 200
