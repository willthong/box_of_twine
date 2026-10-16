"""Conversion between a story's disk JSON and Twine's browser storage records.

The canonical story on disk is the story-format JSON shape Twine consumes when
compiling: ``name``, ``ifid``, ``format``, ``formatVersion``, ``start`` (a
passage name), and a list of ``passages`` each with ``name`` and ``text``.

Twine's own editor keeps stories in ``localStorage`` under a private shape:
``twine-stories-<id>`` holds a story record (``storyFormat``,
``storyFormatVersion``, ``startPassage`` as a passage *id*, and no passages),
and ``twine-passages-<id>`` holds individual passages with an ``id`` and a
``story`` back-reference. These helpers move between the two shapes so the
editor can load a server story and save it back.
"""

import uuid
from datetime import UTC, datetime


def canonical_to_internal(source: dict, story_id: int) -> dict:
    """Convert a disk story into Twine's localStorage records.

    Returns ``{"story": {...}, "passages": [...]}``. Passage ids are minted
    here; the story id is the server's integer id as a string, so the editor
    route ``/stories/<id>`` and the save endpoint agree on it.
    """
    story_id_str = str(story_id)
    start_name = source.get("start") or (
        source["passages"][0]["name"] if source.get("passages") else ""
    )

    passages = []
    start_passage_id = ""
    for passage in source.get("passages", []):
        passage_id = str(uuid.uuid4())
        if passage["name"] == start_name and not start_passage_id:
            start_passage_id = passage_id
        passages.append(
            {
                "id": passage_id,
                "story": story_id_str,
                "name": passage["name"],
                "text": passage.get("text", ""),
                "tags": passage.get("tags", []),
                "left": 0,
                "top": 0,
                "width": 100,
                "height": 100,
                "selected": False,
                "highlighted": False,
            }
        )

    story = {
        "id": story_id_str,
        "name": source["name"],
        "ifid": source.get("ifid", ""),
        "storyFormat": source.get("format", ""),
        "storyFormatVersion": source.get("formatVersion", ""),
        "startPassage": start_passage_id,
        "stylesheet": source.get("stylesheet", ""),
        "script": source.get("script", ""),
        "tags": source.get("tags", []),
        "tagColors": {},
        "snapToGrid": True,
        "selected": False,
        "zoom": 1,
        "lastUpdate": datetime.now(UTC).isoformat(),
    }
    return {"story": story, "passages": passages}


def internal_to_canonical(payload: dict) -> dict:
    """Rebuild the disk story shape from Twine's localStorage records."""
    story = payload["story"]
    passages = payload.get("passages", [])

    start_name = ""
    for passage in passages:
        if passage["id"] == story.get("startPassage"):
            start_name = passage["name"]
            break

    source = {
        "name": story["name"],
        "format": story.get("storyFormat", ""),
        "formatVersion": story.get("storyFormatVersion", ""),
        "start": start_name,
        "passages": [
            _passage_to_source(passage) for passage in passages
        ],
    }
    if story.get("ifid"):
        source["ifid"] = story["ifid"]
    if story.get("tags"):
        source["tags"] = story["tags"]
    if story.get("stylesheet"):
        source["stylesheet"] = story["stylesheet"]
    if story.get("script"):
        source["script"] = story["script"]
    return source


def _passage_to_source(passage: dict) -> dict:
    source = {"name": passage["name"], "text": passage.get("text", "")}
    if passage.get("tags"):
        source["tags"] = passage["tags"]
    return source
