import pytest

from box_of_twine import create_app
from box_of_twine.users import create_user

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "test.sqlite"),
            "DATA_DIR": str(tmp_path / "data"),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(app):
    admin = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    with app.app_context():
        admin["id"] = create_user(admin["username"], admin["password"], is_admin=True)
    return admin
