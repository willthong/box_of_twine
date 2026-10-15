# Compile stories server-side in Python

Publications are produced by our server in Python rather than by the browser
or Node. Twine's publish step is pure string templating: it injects story data
into a story format's HTML via `{{STORY_NAME}}` and `{{STORY_DATA}}`, so we
replicate that replacement server-side and store the resulting standalone
HTML. We rejected uploading the browser's compiled HTML (publishing would
require the editor to be open) and running Node to reuse Twine's compiler (a
second runtime, breaking the one-container goal).
