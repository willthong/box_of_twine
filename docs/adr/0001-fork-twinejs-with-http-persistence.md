# Fork twinejs and add an HTTP persistence backend

We vendor Twine by forking `klembot/twinejs` (GPL-3.0) at a pinned release,
serving its built editor from Flask, and adding a third persistence backend
that saves stories, prefs, and story formats to our REST API instead of the
browser's `localStorage`. We rejected shipping Twine unmodified with
import/export only (no embedded editor) and wrapping the hosted twinery.org
editor in an iframe (its storage is unreachable). The trade-off is maintaining
a fork and re-merging upstream releases; the GPL means our fork's changes stay
GPL, which is acceptable for a self-hosted app.
