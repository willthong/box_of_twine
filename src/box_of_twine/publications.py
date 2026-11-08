import json
import secrets
from pathlib import Path

from flask import Blueprint, Response, current_app, request
from flask_login import current_user, login_required

from .db import get_db
from .stories import OWNER, access_for, owner_id_for, source_path

bp = Blueprint("publications", __name__)

# Twine escapes the values it interpolates into story HTML this way. Using the
# same entities keeps a published story identical to the editor's export.
_HTML_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}


def _escape(value: str) -> str:
    return "".join(_HTML_ESCAPES.get(char, char) for char in value)


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


def _story_data(source: dict) -> str:
    """The ``<tw-storydata>`` markup a story format reads at startup.

    Twine's ``{{STORY_DATA}}`` placeholder expects this element (with its
    ``<tw-passagedata>`` children), not the story's JSON source. Story formats
    such as Harlowe look up ``tw-storydata`` to find the start passage and the
    passage text; without it they render an empty story.
    """
    passages = source.get("passages", [])
    start_name = source.get("start")
    start_node = ""
    passage_html = []
    for pid, passage in enumerate(passages, start=1):
        name = passage.get("name", "")
        tags = " ".join(_escape(tag) for tag in passage.get("tags", []))
        passage_html.append(
            f'<tw-passagedata pid="{pid}" name="{_escape(name)}" tags="{tags}" '
            f'position="{passage.get("left", 0)},{passage.get("top", 0)}" '
            f'size="{passage.get("width", 100)},{passage.get("height", 100)}">'
            f"{_escape(passage.get('text', ''))}</tw-passagedata>"
        )
        if not start_node and name == start_name:
            start_node = str(pid)
    if not start_node and passages:
        start_node = "1"

    story_tags = " ".join(_escape(tag) for tag in source.get("tags", []))
    return (
        f'<tw-storydata name="{_escape(source.get("name", ""))}" '
        f'startnode="{start_node}" creator="Twine" creator-version="2.12.1" '
        f'format="{_escape(source.get("format", ""))}" '
        f'format-version="{_escape(source.get("formatVersion", ""))}" '
        f'ifid="{_escape(source.get("ifid", ""))}" options="" '
        f'tags="{story_tags}" zoom="1" hidden>'
        '<style role="stylesheet" id="twine-user-stylesheet" '
        'type="text/twine-css">'
        f"{source.get('stylesheet', '')}</style>"
        '<script role="script" id="twine-user-script" '
        'type="text/twine-javascript">'
        f"{source.get('script', '')}</script>"
        f"{''.join(passage_html)}</tw-storydata>"
    )


def _compile(source: dict) -> str:
    template = _format_source(source["format"], source["formatVersion"])
    html = template.replace("{{STORY_NAME}}", _escape(source["name"]))
    return html.replace("{{STORY_DATA}}", _story_data(source))


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
