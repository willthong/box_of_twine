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
  var role = data.role || "owner";
  var isPlayback = /^#\/stories\/[^/]+\/(play|proof|test)(\/|$)/.test(
    window.location.hash || ""
  );
  var story = data.story;
  var passages = data.passages || [];

  function showBanner(message) {
    var banner = document.getElementById("box-of-twine-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "box-of-twine-banner";
      banner.setAttribute("role", "status");
      banner.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:2147483647;" +
        "padding:8px 16px;background:#5c2b29;color:#fff;" +
        "font:14px sans-serif;text-align:center;pointer-events:none;";
      var attach = function () {
        document.body.appendChild(banner);
      };
      if (document.body) {
        attach();
      } else {
        document.addEventListener("DOMContentLoaded", attach);
      }
    }
    banner.textContent = message;
    return banner;
  }

  function hideBanner() {
    var banner = document.getElementById("box-of-twine-banner");
    if (banner && banner.parentNode) {
      banner.parentNode.removeChild(banner);
    }
  }

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

  // Passage ids are minted fresh on every shell load, so drop this story's
  // records from earlier sessions before adding the current set. Otherwise the
  // twine-passages index grows on each open and Twine's loader attaches every
  // past copy to the story as a duplicate passage.
  function removeStoryPassages() {
    var ids = (localStorage.getItem("twine-passages") || "")
      .split(",")
      .filter(Boolean);
    var keep = [];
    for (var i = 0; i < ids.length; i++) {
      var raw = localStorage.getItem("twine-passages-" + ids[i]);
      var passage = null;
      if (raw) {
        try {
          passage = JSON.parse(raw);
        } catch (error) {
          passage = null;
        }
      }
      if (passage && passage.story === storyId) {
        localStorage.removeItem("twine-passages-" + ids[i]);
      } else {
        keep.push(ids[i]);
      }
    }
    localStorage.setItem("twine-passages", keep.join(","));
  }

  // Seed Twine's localStorage without clobbering other entries.
  removeStoryPassages();
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
  if (role !== "viewer" && !isPlayback) {
  var saveUrl = "/stories/" + storyId + "/editor";
  var lockUrl = "/stories/" + storyId + "/lock";
  var timer = null;
  var writable = true;
  var holdsLock = false;
  var released = false;

  function stopHeartbeat() {
    if (heartbeat) {
      clearInterval(heartbeat);
      heartbeat = null;
    }
  }

  function addTakeover(banner, holder) {
    var button = document.createElement("button");
    button.id = "box-of-twine-takeover";
    button.type = "button";
    button.textContent = "Take over editing";
    button.style.cssText =
      "pointer-events:auto;margin-left:12px;padding:2px 10px;" +
      "font:inherit;cursor:pointer;";
    var confirming = false;
    button.addEventListener("click", function () {
      if (!confirming) {
        confirming = true;
        button.textContent = "End " + holder + "'s editing session?";
        return;
      }
      button.disabled = true;
      fetch(lockUrl, { method: "DELETE", credentials: "same-origin" })
        .catch(function () {})
        .then(function () {
          return acquire();
        })
        .then(function () {
          if (writable) {
            sync();
          }
        })
        .catch(function () {
          button.disabled = false;
        });
    });
    banner.appendChild(button);
  }

  function block(holder) {
    writable = false;
    holdsLock = false;
    stopHeartbeat();
    var banner = showBanner(
      "This story is being edited by " +
        (holder || "another user") +
        ". Your changes will not be saved."
    );
    if (role === "owner" && holder) {
      addTakeover(banner, holder);
    }
  }

  function deny() {
    writable = false;
    holdsLock = false;
    stopHeartbeat();
    showBanner("You no longer have permission to edit this story.");
  }

  function gone() {
    writable = false;
    holdsLock = false;
    stopHeartbeat();
    showBanner("This story is no longer available.");
  }

  function acquire() {
    return fetch(lockUrl, { method: "POST", credentials: "same-origin" })
      .then(function (response) {
        if (response.status === 409) {
          return response.json().then(function (body) {
            block(body && body.holder);
          });
        }
        if (response.status === 403) {
          deny();
        }
        if (response.status === 404) {
          gone();
        }
        if (response.status === 200) {
          writable = true;
          holdsLock = true;
          released = false;
          hideBanner();
          startHeartbeat();
        }
      })
      .catch(function () {});
  }

  function release() {
    if (!holdsLock || released) {
      return;
    }
    released = true;
    fetch(lockUrl, {
      method: "DELETE",
      credentials: "same-origin",
      keepalive: true,
    }).catch(function () {});
  }

  var heartbeat = null;

  function startHeartbeat() {
    if (heartbeat) {
      return;
    }
    heartbeat = setInterval(function () {
      if (writable) {
        acquire();
      }
    }, 60000);
  }

  startHeartbeat();
  acquire();

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
    })
      .then(function (response) {
        if (response.status === 409) {
          block();
          acquire();
        } else if (response.status === 403) {
          deny();
        } else if (response.status === 404) {
          gone();
        }
      })
      .catch(function () {});
  }

  function sync() {
    if (!writable) {
      return;
    }
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
  window.addEventListener("pagehide", release);
  window.addEventListener("beforeunload", function () {
    sync();
    release();
  });
  }

  // Twine opens Play/Proof/Test in a new window with fragment-only URLs like
  // #/stories/<id>/test/<passageId>. The injected <base href="/static/twine/">
  // makes those resolve to /static/twine/, so point them at the story shell.
  var originalOpen = window.open;
  window.open = function (url, name, features) {
    var match = /^#\/stories\/([^/]+)/.exec(url || "");
    if (match) {
      url = "/stories/" + match[1] + url;
    }
    return originalOpen.call(window, url, name, features);
  };

  // Twine's SPA is a HashRouter, so its editor route is #/stories/<id>. Move
  // /edit/<id> to that path, default a missing hash, and leave deeper routes
  // (play/proof/test) intact so a new window keeps its destination.
  var target = "/stories/" + storyId;
  var hash = "#/stories/" + storyId;
  if (window.location.pathname !== target) {
    history.replaceState(null, "", target + (window.location.hash || hash));
  } else if (!window.location.hash) {
    history.replaceState(null, "", target + hash);
  }

  if (role === "viewer" && !isPlayback) {
    showBanner("You can view this story, but not edit it.");
  }
})();
