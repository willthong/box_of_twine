import json
import time
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, current_app, request, url_for
from flask_login import current_user, login_required

from .db import get_db
from .users import get_user_by_id

bp = Blueprint("stories", __name__)

VIEWER = "viewer"
EDITOR = "editor"
OWNER = "owner"


@dataclass(frozen=True)
class Access:
    """A user's access to a story: the source owner and the user's role."""

    story_owner_id: int
    role: str


def _stories_dir(user_id: int) -> Path:
    return Path(current_app.config["DATA_DIR"]) / "users" / str(user_id) / "stories"


def source_path(user_id: int, story_id: int) -> Path:
    return _stories_dir(user_id) / f"{story_id}.json"


def access_for(story_id: int, user_id: int) -> Access | None:
    """The user's access to the story, or None.

    An admin has full access to everything, so they are treated as an owner of
    any story, whether or not they own it or hold a share on it.
    """
    db = get_db()
    row = db.execute("SELECT owner_id FROM stories WHERE id = ?", (story_id,)).fetchone()
    if row is None:
        return None
    story_owner_id = row["owner_id"]
    if story_owner_id == user_id:
        return Access(story_owner_id, OWNER)
    user = get_user_by_id(user_id)
    if user is not None and user.is_admin:
        return Access(story_owner_id, OWNER)
    share = db.execute(
        "SELECT role FROM shares WHERE story_id = ? AND user_id = ?",
        (story_id, user_id),
    ).fetchone()
    if share is None:
        return None
    return Access(story_owner_id, share["role"])


def owner_id_for(story_id: int, user_id: int) -> int | None:
    """The story's source owner id if *user_id* has owner control of it."""
    access = access_for(story_id, user_id)
    if access is None or access.role != OWNER:
        return None
    return access.story_owner_id


def _lease_expires_at() -> float:
    return time.time() + current_app.config["LOCK_LEASE_SECONDS"]


def _live_lock(story_id: int) -> tuple[int, float] | None:
    """The live lock's (holder_id, expires_at), or None if free or lapsed."""
    row = (
        get_db()
        .execute(
            "SELECT holder_id, expires_at FROM locks WHERE story_id = ?", (story_id,)
        )
        .fetchone()
    )
    if row is None or row["expires_at"] <= time.time():
        return None
    return row["holder_id"], row["expires_at"]


@bp.post("/stories")
@login_required
def create():
    source = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO stories (owner_id, name) VALUES (?, ?)",
        (current_user.id, source["name"]),
    )
    assert cursor.lastrowid is not None
    story_id = cursor.lastrowid
    db.commit()

    path = source_path(current_user.id, story_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(source))
    return {"id": story_id}, 201


@bp.get("/stories")
@login_required
def index():
    rows = (
        get_db()
        .execute(
            "SELECT id, name FROM stories WHERE owner_id = ? ORDER BY id",
            (current_user.id,),
        )
        .fetchall()
    )
    return [{"id": row["id"], "name": row["name"]} for row in rows]


@bp.get("/stories/<int:story_id>")
@login_required
def show(story_id: int):
    access = access_for(story_id, current_user.id)
    if access is None:
        return "", 404
    return json.loads(source_path(access.story_owner_id, story_id).read_text())


@bp.get("/edit/<int:story_id>")
@login_required
def edit(story_id: int):
    # Any role that can read the story may open the editor; writes are still
    # enforced per role at the API seam.
    if access_for(story_id, current_user.id) is None:
        return "", 404

    static_folder = current_app.static_folder
    assert static_folder is not None
    shell = (Path(static_folder) / "twine" / "index.html").read_text()
    base = url_for("static", filename="twine/")
    return shell.replace("<head>", f'<head>\n\t\t<base href="{base}">', 1)


@bp.patch("/stories/<int:story_id>")
@login_required
def update(story_id: int):
    owner_id = owner_id_for(story_id, current_user.id)
    if owner_id is None:
        return "", 404

    name = request.get_json()["name"]
    path = source_path(owner_id, story_id)
    source = json.loads(path.read_text())
    source["name"] = name
    path.write_text(json.dumps(source))

    db = get_db()
    db.execute("UPDATE stories SET name = ? WHERE id = ?", (name, story_id))
    db.commit()
    return "", 200


@bp.put("/stories/<int:story_id>")
@login_required
def save(story_id: int):
    access = access_for(story_id, current_user.id)
    if access is None:
        return "", 404
    if access.role == VIEWER:
        return "", 403

    live = _live_lock(story_id)
    if live is not None and live[0] != current_user.id:
        return "", 409

    source = request.get_json()
    source_path(access.story_owner_id, story_id).write_text(json.dumps(source))

    db = get_db()
    if "name" in source:
        db.execute("UPDATE stories SET name = ? WHERE id = ?", (source["name"], story_id))
    if live is not None:
        db.execute(
            "UPDATE locks SET expires_at = ? WHERE story_id = ?",
            (_lease_expires_at(), story_id),
        )
    db.commit()
    return "", 200


@bp.post("/stories/<int:story_id>/lock")
@login_required
def acquire_lock(story_id: int):
    access = access_for(story_id, current_user.id)
    if access is None:
        return "", 404
    if access.role == VIEWER:
        return "", 403

    live = _live_lock(story_id)
    if live is not None and live[0] != current_user.id:
        holder = get_user_by_id(live[0])
        return {"holder": holder.username if holder is not None else None}, 409

    db = get_db()
    db.execute(
        "INSERT INTO locks (story_id, holder_id, expires_at) VALUES (?, ?, ?) "
        "ON CONFLICT(story_id) DO UPDATE SET holder_id = excluded.holder_id, "
        "expires_at = excluded.expires_at",
        (story_id, current_user.id, _lease_expires_at()),
    )
    db.commit()
    return "", 200


@bp.delete("/stories/<int:story_id>/lock")
@login_required
def break_lock(story_id: int):
    access = access_for(story_id, current_user.id)
    if access is None:
        return "", 404

    live = _live_lock(story_id)
    if live is not None and live[0] != current_user.id and access.role != OWNER:
        return "", 403

    db = get_db()
    db.execute("DELETE FROM locks WHERE story_id = ?", (story_id,))
    db.commit()
    return "", 204


@bp.post("/stories/<int:story_id>/shares")
@login_required
def share(story_id: int):
    if owner_id_for(story_id, current_user.id) is None:
        return "", 404

    data = request.get_json()
    db = get_db()
    db.execute(
        "INSERT INTO shares (story_id, user_id, role) VALUES (?, ?, ?)",
        (story_id, data["user_id"], data["role"]),
    )
    db.commit()
    return "", 201


@bp.delete("/stories/<int:story_id>")
@login_required
def delete(story_id: int):
    owner_id = owner_id_for(story_id, current_user.id)
    if owner_id is None:
        return "", 404

    db = get_db()
    db.execute("DELETE FROM shares WHERE story_id = ?", (story_id,))
    db.execute("DELETE FROM publications WHERE story_id = ?", (story_id,))
    db.execute("DELETE FROM locks WHERE story_id = ?", (story_id,))
    db.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    db.commit()

    source_path(owner_id, story_id).unlink(missing_ok=True)
    return "", 204
