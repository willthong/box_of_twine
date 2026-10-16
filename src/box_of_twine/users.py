import shutil
import sqlite3
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .prefs import current_theme
from .web import login_page_required

bp = Blueprint("users", __name__)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def admin_page_required(view):
    """Admin-only browser route: anonymous to login, others refused.

    The HTML-facing counterpart to :func:`admin_required`: a person who is not
    logged in gets sent to the login page to fix that, while a logged-in user
    without the admin flag is refused outright.
    """

    @login_page_required
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _checked(form, name: str) -> bool:
    """Whether a checkbox submitted *name* as checked.

    The admin form always sends an explicit value for each checkbox, so read
    the value rather than mere presence; absent still means unchecked.
    """
    return any(value == "on" for value in form.getlist(name))


@dataclass
class User(UserMixin):
    id: int
    username: str
    password_hash: str
    is_admin: bool = False
    disabled: bool = False

    @property
    def is_active(self) -> bool:
        return not self.disabled


def _from_row(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        disabled=bool(row["disabled"]),
    )


def get_user_by_id(user_id: int) -> User | None:
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _from_row(row) if row is not None else None


def get_user_by_username(username: str) -> User | None:
    row = (
        get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    )
    return _from_row(row) if row is not None else None


def verify_password(user: User, password: str) -> bool:
    return check_password_hash(user.password_hash, password)


def create_user(username: str, password: str, *, is_admin: bool = False) -> int:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, generate_password_hash(password, method="scrypt"), int(is_admin)),
    )
    db.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def set_password(user_id: int, password: str) -> None:
    """Replace the user's password hash."""
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(password, method="scrypt"), user_id),
    )
    db.commit()


def set_disabled(user_id: int, disabled: bool) -> None:
    """Enable or disable the user's ability to log in."""
    db = get_db()
    db.execute("UPDATE users SET disabled = ? WHERE id = ?", (int(disabled), user_id))
    db.commit()


def set_admin(user_id: int, is_admin: bool) -> None:
    """Grant or revoke the user's admin flag."""
    db = get_db()
    db.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(is_admin), user_id))
    db.commit()


def delete_user(user_id: int) -> None:
    """Hard-delete a user, their stories, and every share or lock they hold.

    That includes the shares and locks on the user's own stories and the ones
    the user holds on other owners' stories.
    """
    db = get_db()
    story_ids = [
        row["id"]
        for row in db.execute("SELECT id FROM stories WHERE owner_id = ?", (user_id,))
    ]
    for story_id in story_ids:
        db.execute("DELETE FROM shares WHERE story_id = ?", (story_id,))
        db.execute("DELETE FROM publications WHERE story_id = ?", (story_id,))
        db.execute("DELETE FROM locks WHERE story_id = ?", (story_id,))
    db.execute("DELETE FROM stories WHERE owner_id = ?", (user_id,))
    # Shares the user holds on other people's stories, and any lock they hold.
    db.execute("DELETE FROM shares WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM locks WHERE holder_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    shutil.rmtree(
        Path(current_app.config["DATA_DIR"]) / "users" / str(user_id),
        ignore_errors=True,
    )


@bp.get("/admin/users")
@admin_page_required
def admin_users():
    users = get_db().execute("SELECT * FROM users ORDER BY id").fetchall()
    return render_template("admin_users.html", theme=current_theme(), users=users)


@bp.post("/admin/users")
@admin_page_required
def create_from_form():
    create_user(
        request.form["username"],
        request.form["password"],
        is_admin=_checked(request.form, "is_admin"),
    )
    return redirect(url_for("users.admin_users"), 303)


@bp.post("/admin/users/<int:user_id>/update")
@admin_page_required
def update_from_form(user_id: int):
    password = request.form.get("password")
    if password:
        set_password(user_id, password)
    set_disabled(user_id, _checked(request.form, "disabled"))
    set_admin(user_id, _checked(request.form, "is_admin"))
    return redirect(url_for("users.admin_users"), 303)


@bp.post("/admin/users/<int:user_id>/delete")
@admin_page_required
def delete_from_form(user_id: int):
    delete_user(user_id)
    return redirect(url_for("users.admin_users"), 303)


@bp.post("/users")
@admin_required
def create():
    data = request.get_json()
    user_id = create_user(
        data["username"], data["password"], is_admin=bool(data.get("is_admin"))
    )
    return {"id": user_id}, 201


@bp.patch("/users/<int:user_id>")
@admin_required
def update(user_id: int):
    data = request.get_json()
    if "password" in data:
        set_password(user_id, data["password"])
    if "disabled" in data:
        set_disabled(user_id, bool(data["disabled"]))
    if "is_admin" in data:
        set_admin(user_id, bool(data["is_admin"]))
    return "", 200


@bp.delete("/users/<int:user_id>")
@admin_required
def delete(user_id: int):
    delete_user(user_id)
    return "", 204


def ensure_admin(username: str | None, password: str | None) -> None:
    if (username is None) != (password is None):
        raise RuntimeError(
            "ADMIN_USERNAME and ADMIN_PASSWORD must both be set or both be unset"
        )
    if not username or not password:
        return

    db = get_db()
    row = db.execute("SELECT 1 FROM users WHERE is_admin = 1 LIMIT 1").fetchone()
    if row is None:
        create_user(username, password, is_admin=True)
