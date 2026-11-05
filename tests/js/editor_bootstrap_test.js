// Regression test for the editor bootstrap's localStorage contract.
//
// Each time the shell is served, the server mints fresh passage IDs (see
// canonical_to_internal). The bootstrap must replace the story's previous
// passage records instead of appending to them, or Twine's loader attaches
// every past copy to the story and the editor shows duplicate passages.
//
// Runs the real editor-bootstrap.js in a sandbox with a persistent fake
// localStorage, then mirrors Twine's loader: every id in `twine-passages`
// whose record exists and points at the story is one passage.

const assert = require("node:assert");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const BOOTSTRAP = fs.readFileSync(
  path.join(
    __dirname,
    "..",
    "..",
    "src",
    "box_of_twine",
    "static",
    "editor-bootstrap.js"
  ),
  "utf8"
);

class Store {
  constructor() {
    this.map = new Map();
  }
  getItem(key) {
    return this.map.has(key) ? this.map.get(key) : null;
  }
  setItem(key, value) {
    this.map.set(key, String(value));
  }
  removeItem(key) {
    this.map.delete(key);
  }
}

function openEditor(store, storyId, passages, options = {}) {
  const location = {
    pathname: options.pathname || `/edit/${storyId}`,
    hash: options.hash || "",
  };
  const openCalls = [];
  const payload = {
    storyId: String(storyId),
    story: {
      id: String(storyId),
      name: "Story",
      storyFormat: "Harlowe",
      storyFormatVersion: "3.3.9",
      startPassage: passages[0].id,
    },
    passages,
  };
  const sandbox = {
    console,
    JSON,
    Math,
    Uint8Array,
    setTimeout: () => 0,
    clearTimeout: () => {},
    localStorage: store,
    history: {
      replaceState(_state, _title, url) {
        const [pathname, hash] = String(url).split("#");
        location.pathname = pathname;
        location.hash = hash ? `#${hash}` : "";
      },
    },
    document: {
      getElementById(id) {
        return id === "box-of-twine-editor-data"
          ? { textContent: JSON.stringify(payload) }
          : null;
      },
    },
    fetch: () => Promise.resolve(),
    crypto: { randomUUID: () => crypto.randomUUID() },
  };
  sandbox.window = sandbox;
  sandbox.window.location = location;
  sandbox.window.open = (url, name, features) => {
    openCalls.push({ url, name, features });
    return {};
  };
  sandbox.window.addEventListener = () => {};
  vm.createContext(sandbox);
  vm.runInContext(BOOTSTRAP, sandbox);
  return { location, sandbox, openCalls };
}

function twinePassagesFor(store, storyId) {
  return (store.getItem("twine-passages") || "")
    .split(",")
    .filter(Boolean)
    .map((id) => store.getItem(`twine-passages-${id}`))
    .filter(Boolean)
    .map((raw) => JSON.parse(raw))
    .filter((passage) => passage.story === String(storyId));
}

function mintPassages(names, storyId) {
  return names.map((name) => ({
    id: crypto.randomUUID(),
    story: String(storyId),
    name,
    text: "",
  }));
}

// Reopening a story must not accumulate passages.
const store = new Store();
for (let open = 1; open <= 3; open++) {
  openEditor(store, 1, mintPassages(["Start", "Gate"], 1));
  const loaded = twinePassagesFor(store, 1);
  assert.strictEqual(
    loaded.length,
    2,
    `after open ${open}, Twine would load ${loaded.length} passages ` +
      `(${loaded.map((p) => p.name).join(",")}), expected 2`
  );
}

// Replacing one story's passages must leave other stories alone.
openEditor(store, 2, mintPassages(["Other"], 2));
openEditor(store, 1, mintPassages(["Start", "Gate"], 1));
assert.strictEqual(
  twinePassagesFor(store, 2).length,
  1,
  "opening story 1 must not remove story 2's passages"
);
assert.strictEqual(
  twinePassagesFor(store, 1).length,
  2,
  "opening story 1 must leave exactly its own two passages"
);

// Twine opens Play/Proof/Test as fragment-only URLs; the injected
// <base href="/static/twine/"> would otherwise send them to /static/twine/.
const opener = openEditor(new Store(), 6, mintPassages(["Start"], 6));
opener.sandbox.window.open("#/stories/6/test/passage-1", "_blank");
assert.strictEqual(
  opener.openCalls.at(-1).url,
  "/stories/6#/stories/6/test/passage-1",
  "test links must open the story shell, not /static/twine/"
);
opener.sandbox.window.open("#/stories/6/play", "_blank");
assert.strictEqual(
  opener.openCalls.at(-1).url,
  "/stories/6#/stories/6/play",
  "play links must open the story shell"
);
opener.sandbox.window.open("https://example.com/x", "_blank");
assert.strictEqual(
  opener.openCalls.at(-1).url,
  "https://example.com/x",
  "non-Twine links must pass through unchanged"
);

// A bare /stories/<id> load still has to land on the story route.
const bare = openEditor(new Store(), 6, mintPassages(["Start"], 6), {
  pathname: "/stories/6",
  hash: "",
});
assert.deepStrictEqual(
  bare.location,
  { pathname: "/stories/6", hash: "#/stories/6" },
  "a bare story URL must default to the story hash route"
);

// Moving /edit/<id> to /stories/<id> must keep a deep route.
const fromEdit = openEditor(new Store(), 6, mintPassages(["Start"], 6), {
  pathname: "/edit/6",
  hash: "#/stories/6/test/passage-1",
});
assert.deepStrictEqual(
  fromEdit.location,
  { pathname: "/stories/6", hash: "#/stories/6/test/passage-1" },
  "moving /edit to /stories must preserve a deep route"
);

// A deeper hash route on the canonical path must survive the shell load.
const deep = openEditor(new Store(), 6, mintPassages(["Start"], 6), {
  pathname: "/stories/6",
  hash: "#/stories/6/test/passage-1",
});
assert.deepStrictEqual(
  deep.location,
  { pathname: "/stories/6", hash: "#/stories/6/test/passage-1" },
  "loading the shell must not rewrite a test route back to the story"
);

console.log("editor bootstrap preserves story storage and Twine routes");
