/* Wire the vendored Twine editor to the server-side story store.

   The page embeds a <script type="application/json" id="box-of-twine-editor-data">
   holding the story in Twine's internal localStorage shape. This script runs
   before Twine's bundle (which is a deferred module), seeds localStorage, then
   points the editor at /stories/<id> and persists edits back to the server.
*/
(function () {
  "use strict";

  var dataEl = document.getElementById("box-of-twine-editor-data");
  if (!dataEl) {
    return;
  }

  var data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (error) {
    return;
  }

  var storyId = data.storyId;
  var story = data.story;
  var passages = data.passages || [];

  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    var bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < 16; i++) {
        bytes[i] = Math.floor(Math.random() * 256);
      }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = [];
    for (var j = 0; j < 16; j++) {
      hex.push((bytes[j] + 0x100).toString(16).substring(1));
    }
    return (
      hex.slice(0, 4).join("") +
      "-" +
      hex.slice(4, 6).join("") +
      "-" +
      hex.slice(6, 8).join("") +
      "-" +
      hex.slice(8, 10).join("") +
      "-" +
      hex.slice(10, 16).join("")
    );
  }

  function addId(list, id) {
    var ids = list ? list.split(",").filter(Boolean) : [];
    if (ids.indexOf(id) === -1) {
      ids.push(id);
    }
    return ids.join(",");
  }

  // Seed Twine's localStorage without clobbering other entries.
  localStorage.setItem(
    "twine-stories",
    addId(localStorage.getItem("twine-stories"), storyId)
  );
  localStorage.setItem("twine-stories-" + storyId, JSON.stringify(story));

  var passageIds = passages.map(function (passage) {
    return passage.id;
  });
  localStorage.setItem(
    "twine-passages",
    passageIds.reduce(
      function (list, id) {
        return addId(list, id);
      },
      localStorage.getItem("twine-passages")
    )
  );
  passages.forEach(function (passage) {
    localStorage.setItem("twine-passages-" + passage.id, JSON.stringify(passage));
  });

  // Skip Twine's first-run welcome so the editor route renders directly.
  function ensurePref(name, value) {
    var list = localStorage.getItem("twine-prefs") || "";
    var ids = list ? list.split(",").filter(Boolean) : [];
    for (var i = 0; i < ids.length; i++) {
      var raw = localStorage.getItem("twine-prefs-" + ids[i]);
      if (!raw) {
        continue;
      }
      var pref;
      try {
        pref = JSON.parse(raw);
      } catch (error) {
        continue;
      }
      if (pref.name === name) {
        pref.value = value;
        localStorage.setItem("twine-prefs-" + ids[i], JSON.stringify(pref));
        return;
      }
    }
    var id = uuid();
    localStorage.setItem(
      "twine-prefs-" + id,
      JSON.stringify({ id: id, name: name, value: value })
    );
    localStorage.setItem("twine-prefs", addId(list, id));
  }
  ensurePref("welcomeSeen", true);

  // Persist edits back to the server.
  var saveUrl = "/stories/" + storyId + "/editor";
  var timer = null;

  function collect() {
    var storyRaw = localStorage.getItem("twine-stories-" + storyId);
    if (!storyRaw) {
      return null;
    }
    var storyRecord;
    try {
      storyRecord = JSON.parse(storyRaw);
    } catch (error) {
      return null;
    }

    var ids = (localStorage.getItem("twine-passages") || "")
      .split(",")
      .filter(Boolean);
    var passages = [];
    for (var i = 0; i < ids.length; i++) {
      var raw = localStorage.getItem("twine-passages-" + ids[i]);
      if (!raw) {
        continue;
      }
      var passage;
      try {
        passage = JSON.parse(raw);
      } catch (error) {
        continue;
      }
      if (passage.story === storyId) {
        passages.push(passage);
      }
    }
    return { story: storyRecord, passages: passages };
  }

  function send(payload) {
    fetch(saveUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "same-origin",
      keepalive: true,
    });
  }

  function sync() {
    var payload = collect();
    if (payload) {
      send(payload);
    }
  }

  function schedule() {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(sync, 300);
  }

  var originalSetItem = localStorage.setItem.bind(localStorage);
  var originalRemoveItem = localStorage.removeItem.bind(localStorage);

  localStorage.setItem = function (key, value) {
    originalSetItem(key, value);
    if (typeof key === "string" && key.indexOf("twine-") === 0) {
      schedule();
    }
  };
  localStorage.removeItem = function (key) {
    originalRemoveItem(key);
    if (typeof key === "string" && key.indexOf("twine-") === 0) {
      schedule();
    }
  };
  window.addEventListener("beforeunload", sync);

  // Twine's editor route is /stories/<id>; land there instead of /edit/<id>.
  var target = "/stories/" + storyId;
  if (window.location.pathname !== target) {
    history.replaceState(null, "", target);
  }
})();
