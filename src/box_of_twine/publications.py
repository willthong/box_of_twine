import json
import secrets
from pathlib import Path

from flask import Blueprint, Response, current_app, request
from flask_login import current_user, login_required

from .db import get_db
from .stories import OWNER, access_for, owner_id_for, source_path

bp = Blueprint("publications", __name__)


def _format_source(format_name: str, version: str) -> str:
    """The story format's HTML template, extracted from its ``format.js``."""
    static_folder = current_app.static_folder
    assert static_folder is not None
    path = (
        Path(static_folder)
        / "twine"
        / "story-formats"
        / f"{format_name.lower()}-{version}"
        / "format.js"
    )
    text = path.read_text()
    marker = text.index('"source"')
    start = text.index(":", marker) + 1
    while text[start].isspace():
        start += 1
    source, _ = json.JSONDecoder().raw_decode(text, start)
    return source


def _compile(source: dict) -> str:
    template = _format_source(source["format"], source["formatVersion"])
    html = template.replace("{{STORY_NAME}}", source["name"])
    return html.replace("{{STORY_DATA}}", json.dumps(source))


@bp.post("/stories/<int:story_id>/publications")
@login_required
def create(story_id: int):
    owner_id = owner_id_for(story_id, current_user.id)
    if owner_id is None:
        return "", 404

    visibility = request.get_json()["visibility"]
    source = json.loads(source_path(owner_id, story_id).read_text())
    slug = secrets.token_urlsafe(12)

    db = get_db()
    db.execute(
        "INSERT INTO publications (story_id, slug, visibility, html) VALUES (?, ?, ?, ?)",
        (story_id, slug, visibility, _compile(source)),
    )
    db.commit()
    return {"slug": slug}, 201


@bp.get("/p/<slug>")
def show(slug: str):
    row = (
        get_db()
        .execute(
            "SELECT story_id, visibility, html FROM publications WHERE slug = ?",
            (slug,),
        )
        .fetchone()
    )
    if row is None:
        return "", 404

    visibility = row["visibility"]
    if visibility != "public":
        if not current_user.is_authenticated:
            return "", 404
        access = access_for(row["story_id"], current_user.id)
        if access is None:
            return "", 404
        if visibility == "private" and access.role != OWNER:
            return "", 404

    return Response(row["html"], mimetype="text/html")
