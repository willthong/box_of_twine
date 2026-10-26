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

function openEditor(store, storyId, passages) {
  const location = { pathname: `/edit/${storyId}`, hash: "" };
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
  sandbox.window.addEventListener = () => {};
  vm.createContext(sandbox);
  vm.runInContext(BOOTSTRAP, sandbox);
  return location;
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

console.log("editor bootstrap replaces a story's passages instead of appending");
