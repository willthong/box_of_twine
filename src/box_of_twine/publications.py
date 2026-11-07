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


@bp.post("/stories/<int:story_id>/public-link")
@login_required
def create_link(story_id: int):
    if owner_id_for(story_id, current_user.id) is None:
        return "", 404

    db = get_db()
    slug = secrets.token_urlsafe(12)
    db.execute(
        "INSERT INTO public_links (story_id, slug) VALUES (?, ?) "
        "ON CONFLICT(story_id) DO NOTHING",
        (story_id, slug),
    )
    db.commit()
    row = db.execute(
        "SELECT slug FROM public_links WHERE story_id = ?", (story_id,)
    ).fetchone()
    assert row is not None
    return {"slug": row["slug"]}, 201


@bp.get("/stories/<int:story_id>/public-link")
@login_required
def read_link(story_id: int):
    if access_for(story_id, current_user.id) is None:
        return "", 404

    row = (
        get_db()
        .execute("SELECT slug FROM public_links WHERE story_id = ?", (story_id,))
        .fetchone()
    )
    return {"slug": row["slug"] if row is not None else None}


@bp.delete("/stories/<int:story_id>/public-link")
@login_required
def revoke_link(story_id: int):
    if owner_id_for(story_id, current_user.id) is None:
        return "", 404

    db = get_db()
    db.execute("DELETE FROM public_links WHERE story_id = ?", (story_id,))
    db.commit()
    return "", 204


@bp.get("/public/<slug>")
def show_public(slug: str):
    row = (
        get_db()
        .execute(
            "SELECT stories.owner_id, public_links.story_id FROM public_links "
            "JOIN stories ON stories.id = public_links.story_id "
            "WHERE public_links.slug = ?",
            (slug,),
        )
        .fetchone()
    )
    if row is None:
        return "", 404

    source = json.loads(source_path(row["owner_id"], row["story_id"]).read_text())
    return Response(_compile(source), mimetype="text/html")


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
