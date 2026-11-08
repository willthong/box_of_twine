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

function makeElement(tagName) {
  return {
    tagName: String(tagName).toUpperCase(),
    style: {},
    dataset: {},
    textContent: "",
    id: "",
    children: [],
    parentNode: null,
    listeners: {},
    appendChild(child) {
      child.parentNode = this;
      this.children.push(child);
      return child;
    },
    removeChild(child) {
      this.children = this.children.filter((entry) => entry !== child);
      child.parentNode = null;
    },
    remove() {
      if (this.parentNode) {
        this.parentNode.removeChild(this);
      }
    },
    setAttribute(name, value) {
      this[name] = value;
    },
    addEventListener(type, callback) {
      this.listeners[type] = callback;
    },
  };
}

function findById(root, id) {
  if (root.id === id) {
    return root;
  }
  for (const child of root.children) {
    const found = findById(child, id);
    if (found) {
      return found;
    }
  }
  return null;
}

function makeDom(payload) {
  const documentListeners = {};
  const body = makeElement("body");
  const documentElement = makeElement("html");
  documentElement.appendChild(body);
  const dataElement = makeElement("script");
  dataElement.id = "box-of-twine-editor-data";
  dataElement.textContent = JSON.stringify(payload);
  const elements = new Map([[dataElement.id, dataElement]]);
  return {
    body,
    documentListeners,
    elements,
    document: {
      body,
      documentElement,
      getElementById(id) {
        return elements.get(id) || findById(documentElement, id);
      },
      createElement: makeElement,
      addEventListener(type, callback) {
        documentListeners[type] = callback;
      },
    },
  };
}

function makeTimers() {
  const timeouts = [];
  const intervals = [];
  return {
    timeouts,
    intervals,
    setTimeout(callback, delay) {
      const timer = { callback, delay, cleared: false };
      timeouts.push(timer);
      return timer;
    },
    clearTimeout(timer) {
      if (timer) {
        timer.cleared = true;
      }
    },
    setInterval(callback, delay) {
      const timer = { callback, delay, cleared: false };
      intervals.push(timer);
      return timer;
    },
    clearInterval(timer) {
      if (timer) {
        timer.cleared = true;
      }
    },
    runTimeouts() {
      const pending = timeouts.filter((timer) => !timer.cleared);
      pending.forEach((timer) => timer.callback());
    },
    runIntervals() {
      intervals
        .filter((timer) => !timer.cleared)
        .forEach((timer) => timer.callback());
    },
  };
}

function makeResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

function makeFetch(handler = () => makeResponse(200, {})) {
  const calls = [];
  const fetch = (url, options = {}) => {
    const call = { url, options, method: options.method || "GET" };
    calls.push(call);
    return Promise.resolve(handler(call));
  };
  fetch.calls = calls;
  return fetch;
}

function openEditor(store, storyId, passages, options = {}) {
  const location = {
    pathname: options.pathname || `/edit/${storyId}`,
    hash: options.hash || "",
  };
  const openCalls = [];
  const payload = {
    storyId: String(storyId),
    role: options.role || "owner",
    story: {
      id: String(storyId),
      name: "Story",
      storyFormat: "Harlowe",
      storyFormatVersion: "3.3.9",
      startPassage: passages[0].id,
    },
    passages,
  };
  const timers = makeTimers();
  const fetch = options.fetch || makeFetch();
  const dom = makeDom(payload);
  const windowListeners = {};
  const sandbox = {
    console,
    JSON,
    Math,
    Uint8Array,
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    setInterval: timers.setInterval,
    clearInterval: timers.clearInterval,
    localStorage: store,
    history: {
      replaceState(_state, _title, url) {
        const [pathname, hash] = String(url).split("#");
        location.pathname = pathname;
        location.hash = hash ? `#${hash}` : "";
      },
    },
    document: dom.document,
    fetch,
    crypto: { randomUUID: () => crypto.randomUUID() },
  };
  sandbox.window = sandbox;
  sandbox.window.location = location;
  sandbox.window.open = (url, name, features) => {
    openCalls.push({ url, name, features });
    return {};
  };
  sandbox.window.addEventListener = (type, callback) => {
    windowListeners[type] = callback;
  };
  vm.createContext(sandbox);
  vm.runInContext(BOOTSTRAP, sandbox);
  if (dom.documentListeners.DOMContentLoaded) {
    dom.documentListeners.DOMContentLoaded();
  }
  return {
    location,
    sandbox,
    openCalls,
    fetch,
    timers,
    dom,
    windowListeners,
    banner: () => findById(dom.body, "box-of-twine-banner"),
  };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

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

(async () => {
  // A viewer must never take the lock or send story edits, and must be told
  // the editor is read-only.
  const viewerStore = new Store();
  const viewerFetch = makeFetch();
  const viewer = openEditor(viewerStore, 7, mintPassages(["Start", "Gate"], 7), {
    role: "viewer",
    fetch: viewerFetch,
  });
  await flush();

  assert.strictEqual(
    viewerFetch.calls.length,
    0,
    "opening the editor as a viewer must not call the lock or save endpoints"
  );

  // Twine still writes localStorage; the viewer bootstrap must not persist it.
  viewerStore.setItem(
    "twine-stories-7",
    JSON.stringify({ id: "7", name: "Changed by a viewer" })
  );
  viewer.timers.runTimeouts();
  await flush();
  assert.strictEqual(
    viewerFetch.calls.filter((call) => call.method === "PUT").length,
    0,
    "a viewer's edits must never be sent to the save endpoint"
  );

  const viewerBanner = viewer.banner();
  assert.ok(viewerBanner, "viewers must see a read-only banner");
  assert.match(
    viewerBanner.textContent,
    /not edit/i,
    "the viewer banner must explain that editing is unavailable"
  );

  // A writer takes the story's edit lock on entering the editor.
  const writerStore = new Store();
  const writerFetch = makeFetch(() => makeResponse(200, {}));
  const writer = openEditor(writerStore, 8, mintPassages(["Start"], 8), {
    role: "editor",
    fetch: writerFetch,
  });
  await flush();

  assert.strictEqual(
    writerFetch.calls.filter(
      (call) => call.url === "/stories/8/lock" && call.method === "POST"
    ).length,
    1,
    "an editor must acquire the lock on entering the editor"
  );

  // The lock is renewed on a heartbeat while the editor remains writable.
  assert.strictEqual(
    writer.timers.intervals.filter((timer) => timer.delay === 60000).length,
    1,
    "a writer must have a 60-second lock heartbeat"
  );
  writer.timers.runIntervals();
  await flush();
  assert.strictEqual(
    writerFetch.calls.filter(
      (call) => call.url === "/stories/8/lock" && call.method === "POST"
    ).length,
    2,
    "the heartbeat must renew the lock"
  );

  // Closing the editor releases the lock once.
  assert.ok(writer.windowListeners.pagehide, "the editor must release on pagehide");
  writer.windowListeners.pagehide();
  await flush();
  assert.strictEqual(
    writerFetch.calls.filter(
      (call) => call.url === "/stories/8/lock" && call.method === "DELETE"
    ).length,
    1,
    "leaving the editor must release the lock"
  );
  writer.windowListeners.beforeunload();
  await flush();
  assert.strictEqual(
    writerFetch.calls.filter(
      (call) => call.url === "/stories/8/lock" && call.method === "DELETE"
    ).length,
    1,
    "releasing twice must not send a second DELETE"
  );

  // When someone else holds the lock, the editor names them and stops
  // sending edits.
  const lockedStore = new Store();
  const lockedFetch = makeFetch((call) =>
    call.url === "/stories/9/lock" && call.method === "POST"
      ? makeResponse(409, { holder: "bob" })
      : makeResponse(200, {})
  );
  const locked = openEditor(lockedStore, 9, mintPassages(["Start"], 9), {
    role: "editor",
    fetch: lockedFetch,
  });
  await flush();

  const lockedBanner = locked.banner();
  assert.ok(lockedBanner, "a blocked editor must see a banner");
  assert.match(
    lockedBanner.textContent,
    /being edited by bob/i,
    "the banner must name the lock holder"
  );
  assert.match(
    lockedBanner.textContent,
    /will not be saved/i,
    "the banner must warn that edits will not be saved"
  );

  assert.strictEqual(
    findById(lockedBanner, "box-of-twine-takeover"),
    null,
    "a plain editor must not be offered a lock takeover"
  );

  lockedStore.setItem(
    "twine-stories-9",
    JSON.stringify({ id: "9", name: "Blocked edit" })
  );
  locked.timers.runTimeouts();
  await flush();
  assert.strictEqual(
    lockedFetch.calls.filter((call) => call.method === "PUT").length,
    0,
    "a blocked editor must not send story edits"
  );

  assert.strictEqual(
    locked.timers.intervals.filter((timer) => !timer.cleared).length,
    0,
    "a blocked editor must stop its lock heartbeat"
  );

  locked.windowListeners.pagehide();
  await flush();
  assert.strictEqual(
    lockedFetch.calls.filter((call) => call.method === "DELETE").length,
    0,
    "a blocked editor must not release someone else's lock"
  );

  // If the lock is lost after entering, the next save reports a conflict and
  // the editor switches to the same blocked state.
  const conflictStore = new Store();
  let conflictLockPosts = 0;
  const conflictFetch = makeFetch((call) => {
    if (call.url === "/stories/10/lock" && call.method === "POST") {
      conflictLockPosts += 1;
      return conflictLockPosts === 1
        ? makeResponse(200, {})
        : makeResponse(409, { holder: "bob" });
    }
    if (call.method === "PUT") {
      return makeResponse(409, {});
    }
    return makeResponse(200, {});
  });
  const conflicted = openEditor(
    conflictStore,
    10,
    mintPassages(["Start"], 10),
    { role: "editor", fetch: conflictFetch }
  );
  await flush();

  conflictStore.setItem(
    "twine-stories-10",
    JSON.stringify({ id: "10", name: "Losing edit" })
  );
  conflicted.timers.runTimeouts();
  await flush();

  const conflictBanner = conflicted.banner();
  assert.ok(conflictBanner, "a save conflict must show the blocked banner");
  assert.match(
    conflictBanner.textContent,
    /being edited by bob/i,
    "a save conflict must name the current lock holder"
  );

  conflictStore.setItem(
    "twine-stories-10",
    JSON.stringify({ id: "10", name: "Later edit" })
  );
  conflicted.timers.runTimeouts();
  await flush();
  assert.strictEqual(
    conflictFetch.calls.filter((call) => call.method === "PUT").length,
    1,
    "a save conflict must stop later saves"
  );

  // A story that disappears while open is reported plainly.
  const goneStore = new Store();
  const goneFetch = makeFetch((call) =>
    call.url === "/stories/11/lock" && call.method === "POST"
      ? makeResponse(404, {})
      : makeResponse(200, {})
  );
  const gone = openEditor(goneStore, 11, mintPassages(["Start"], 11), {
    role: "editor",
    fetch: goneFetch,
  });
  await flush();

  const goneBanner = gone.banner();
  assert.ok(goneBanner, "a deleted story must show a banner");
  assert.match(
    goneBanner.textContent,
    /no longer available/i,
    "the banner must say the story is gone"
  );

  // Play/Proof/Test windows are playback: no lock and no saving.
  const playStore = new Store();
  const playFetch = makeFetch();
  const play = openEditor(playStore, 12, mintPassages(["Start"], 12), {
    role: "editor",
    fetch: playFetch,
    hash: "#/stories/12/play",
  });
  await flush();

  assert.strictEqual(
    playFetch.calls.length,
    0,
    "a playback window must not take the lock or save the story"
  );
  playStore.setItem(
    "twine-stories-12",
    JSON.stringify({ id: "12", name: "Playback edit" })
  );
  play.timers.runTimeouts();
  await flush();
  assert.strictEqual(
    playFetch.calls.filter((call) => call.method === "PUT").length,
    0,
    "a playback window must never send story edits"
  );

  // An owner can displace the current holder after an inline confirmation,
  // then the editor re-acquires and flushes edits made while blocked.
  const takeoverStore = new Store();
  let takeoverLockPosts = 0;
  const takeoverFetch = makeFetch((call) => {
    if (call.url === "/stories/13/lock") {
      if (call.method === "DELETE") {
        return makeResponse(204, {});
      }
      if (call.method === "POST") {
        takeoverLockPosts += 1;
        return takeoverLockPosts === 1
          ? makeResponse(409, { holder: "bob" })
          : makeResponse(200, {});
      }
    }
    return makeResponse(200, {});
  });
  const takeover = openEditor(
    takeoverStore,
    13,
    mintPassages(["Start"], 13),
    { role: "owner", fetch: takeoverFetch }
  );
  await flush();

  const takeoverBanner = takeover.banner();
  const takeoverButton = findById(takeoverBanner, "box-of-twine-takeover");
  assert.ok(takeoverButton, "an owner must be offered a lock takeover");
  assert.match(takeoverButton.textContent, /take over/i);

  takeoverButton.listeners.click();
  await flush();
  assert.strictEqual(
    takeoverFetch.calls.filter((call) => call.method === "DELETE").length,
    0,
    "the first click must ask for confirmation, not break the lock"
  );
  assert.match(
    takeoverButton.textContent,
    /bob/i,
    "the confirmation must name the displaced editor"
  );

  takeoverButton.listeners.click();
  await flush();
  assert.strictEqual(
    takeoverFetch.calls.filter((call) => call.method === "DELETE").length,
    1,
    "confirming a takeover must break the current lock"
  );
  assert.strictEqual(
    takeoverLockPosts,
    2,
    "confirming a takeover must re-acquire the lock"
  );
  assert.strictEqual(
    takeover.banner(),
    null,
    "a successful takeover must clear the blocked banner"
  );
  assert.strictEqual(
    takeoverFetch.calls.filter((call) => call.method === "PUT").length,
    1,
    "a successful takeover must flush edits made while blocked"
  );

  assert.strictEqual(
    takeover.timers.intervals.filter(
      (timer) => !timer.cleared && timer.delay === 60000
    ).length,
    1,
    "a successful takeover must resume the lock heartbeat"
  );

  // Losing write permission is reported as a permission problem, not as
  // someone else's lock.
  const revokedStore = new Store();
  const revokedFetch = makeFetch((call) =>
    call.url === "/stories/14/lock" && call.method === "POST"
      ? makeResponse(403, {})
      : makeResponse(200, {})
  );
  const revoked = openEditor(revokedStore, 14, mintPassages(["Start"], 14), {
    role: "editor",
    fetch: revokedFetch,
  });
  await flush();
  assert.match(
    revoked.banner().textContent,
    /no longer have permission/i,
    "a 403 must explain that write access was revoked"
  );

  console.log("editor bootstrap preserves story storage and Twine routes");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
