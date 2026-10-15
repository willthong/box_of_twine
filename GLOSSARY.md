# Box of Twine

A self-hosted, multi-user web app that vendors the Twine editor, stores each
user's stories on the server, lets users share stories with each other, and
publishes compiled stories to the web.

## Stories

**Story**:
A Twine story: a titled set of linked passages plus metadata (start passage,
story format, stylesheet, script). A user authors stories; each lives as a JSON
file in the user's folder.
_Avoid_: project, game, document, work

**Passage**:
A named chunk of text within a story, optionally linked to other passages.
_Avoid_: page, node, card, scene, slide

**Compile**:
To produce a self-contained, playable HTML file from a story and a story format.
_Avoid_: build, render, generate, export

## Access

**User**:
A person with a login to Box of Twine, identified by a username and a password.
Users own stories.
_Avoid_: account, member

**Admin**:
A user with the admin flag, who can create, disable, and delete users, and who
has full access to everything.
_Avoid_: root, superuser, operator

**Share**:
A grant of a role on a story from an owner to another user.
_Avoid_: permission, access grant, invite

**Role**:
The access level a share confers on a story: `viewer` (read-only), `editor`
(read + edit), or `owner` (full control).
_Avoid_: permission, access level, privilege

**Owner**:
The role with full control of a story: view, edit, share, publish, delete, and
transfer. A story may have multiple co-equal owners.
_Avoid_: manager, author, creator, admin

**Lock**:
The per-story lease held by the one user currently editing, which blocks other
writes and expires if not renewed.
_Avoid_: checkout, mutex, reservation

## Publication

**Publication**:
An immutable compiled HTML artifact of a story, with a visibility and a stable
URL.
_Avoid_: release, build, export, publish

**Visibility**:
The audience of a publication: `private` (owner), `shared` (named users), or
`public` (anyone with the URL).
_Avoid_: scope, audience, privacy
