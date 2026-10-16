from flask import Blueprint, request
from flask_login import current_user, login_required

from .db import get_db

bp = Blueprint("prefs", __name__)


def stored_theme(user_id: int) -> str | None:
    row = (
        get_db()
        .execute("SELECT theme FROM prefs WHERE user_id = ?", (user_id,))
        .fetchone()
    )
    return row["theme"] if row is not None else None


def current_theme() -> str | None:
    """The signed-in user's stored theme, or None for an anonymous visitor."""
    if not current_user.is_authenticated:
        return None
    return stored_theme(current_user.id)


def set_theme(user_id: int, theme: str) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO prefs (user_id, theme) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET theme = excluded.theme",
        (user_id, theme),
    )
    db.commit()


@bp.patch("/prefs")
@login_required
def update():
    set_theme(current_user.id, request.get_json()["theme"])
    return "", 204
