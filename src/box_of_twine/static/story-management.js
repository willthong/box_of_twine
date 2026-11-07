/* Story rename, sharing, and public-link management on the home page.

   The page is server-rendered; this module talks to the JSON seams and updates
   the open dialog in place, so an action never reloads the page. */

const page = document.querySelector("[data-current-user-id]");
const currentUserId = page ? Number(page.dataset.currentUserId) : null;

const renameDialog = document.getElementById("rename-dialog");
const sharesDialog = document.getElementById("shares-dialog");
const publicLinkDialog = document.getElementById("public-link-dialog");

const renameForm = renameDialog && renameDialog.querySelector("[data-rename-form]");
const shareGrantForm =
  sharesDialog && sharesDialog.querySelector("[data-share-grant]");
const shareUsers = sharesDialog && sharesDialog.querySelector("[data-share-users]");
const shareList = sharesDialog && sharesDialog.querySelector("[data-share-list]");
const publicLinkStatus = publicLinkDialog
  ? publicLinkDialog.querySelector("[data-public-link-status]")
  : null;
const publicLinkUrl = publicLinkDialog
  ? publicLinkDialog.querySelector("[data-public-link-url]")
  : null;
const publicLinkCopy = publicLinkDialog
  ? publicLinkDialog.querySelector("[data-public-link-copy]")
  : null;
const publicLinkRevoke = publicLinkDialog
  ? publicLinkDialog.querySelector("[data-public-link-revoke]")
  : null;

let currentStory = null;

async function request(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body && body.error) {
        message = body.error;
      }
    } catch (error) {
      // The API often uses empty bodies for failures.
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return null;
  }
  const type = response.headers.get("content-type") || "";
  return type.includes("application/json") ? response.json() : null;
}

function showError(dialog, message) {
  const error = dialog && dialog.querySelector("[data-error]");
  if (!error) {
    return;
  }
  error.textContent = message || "";
  error.hidden = !message;
}

function clearError(dialog) {
  showError(dialog, "");
}

function roleSelect(value) {
  const select = document.createElement("select");
  select.setAttribute("data-share-change", "");
  select.setAttribute("aria-label", "Role");
  for (const role of ["viewer", "editor", "owner"]) {
    const option = document.createElement("option");
    option.value = role;
    option.textContent = role;
    option.selected = role === value;
    select.append(option);
  }
  return select;
}

function renderShares(shares) {
  if (!shareList) {
    return;
  }
  shareList.replaceChildren();
  if (!shares.length) {
    const empty = document.createElement("li");
    empty.className = "share-empty";
    empty.textContent = "No one else has access yet.";
    shareList.append(empty);
    return;
  }
  for (const share of shares) {
    const row = document.createElement("li");
    row.className = "share-row";
    row.dataset.userId = String(share.user_id);

    const name = document.createElement("span");
    name.className = "share-username";
    name.textContent = share.username;

    const select = roleSelect(share.role);
    select.addEventListener("change", async () => {
      clearError(sharesDialog);
      try {
        await request(`/stories/${currentStory.id}/shares`, {
          method: "POST",
          body: JSON.stringify({
            user_id: share.user_id,
            role: select.value,
          }),
        });
        await loadShares(currentStory.id);
      } catch (error) {
        showError(sharesDialog, error.message);
      }
    });

    const revoke = document.createElement("md-text-button");
    revoke.type = "button";
    revoke.textContent = "Remove";
    revoke.dataset.shareRevoke = "";
    revoke.addEventListener("click", async () => {
      clearError(sharesDialog);
      try {
        await request(
          `/stories/${currentStory.id}/shares/${share.user_id}`,
          { method: "DELETE" }
        );
        await loadShares(currentStory.id);
      } catch (error) {
        showError(sharesDialog, error.message);
      }
    });

    row.append(name, select, revoke);
    shareList.append(row);
  }
}

async function loadShares(storyId) {
  const shares = await request(`/stories/${storyId}/shares`);
  renderShares(shares || []);
}

async function loadShareUsers() {
  if (!shareUsers) {
    return;
  }
  const users = await request("/users");
  shareUsers.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose a user";
  shareUsers.append(placeholder);

  const candidates = (users || []).filter(
    (user) => user.id !== currentUserId && !user.disabled
  );
  for (const user of candidates) {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.username;
    shareUsers.append(option);
  }
  shareUsers.disabled = candidates.length === 0;
}

async function openRename(story) {
  clearError(renameDialog);
  const field = renameForm && renameForm.querySelector('[name="name"]');
  if (field) {
    field.value = story.name;
  }
  renameDialog.showModal();
}

async function openShares(story) {
  clearError(sharesDialog);
  if (shareList) {
    shareList.replaceChildren();
  }
  sharesDialog.showModal();
  try {
    await Promise.all([loadShareUsers(), loadShares(story.id)]);
  } catch (error) {
    showError(sharesDialog, error.message);
  }
}

function setPublicLinkDialog(slug, story) {
  const isOwner = story.role === "owner";
  const url = slug ? `${window.location.origin}/public/${slug}` : "";
  if (publicLinkUrl) {
    publicLinkUrl.value = url;
  }
  if (publicLinkCopy) {
    publicLinkCopy.disabled = !url;
  }
  if (publicLinkRevoke) {
    publicLinkRevoke.hidden = !(isOwner && url);
  }
  if (publicLinkStatus) {
    if (url) {
      publicLinkStatus.textContent = "Anyone with this link can play the latest story.";
    } else {
      publicLinkStatus.textContent =
        "No public link has been created for this story yet.";
    }
  }
}

async function copyPublicLink() {
  if (!publicLinkUrl || !publicLinkUrl.value) {
    return;
  }
  const text = publicLinkUrl.value;
  try {
    await navigator.clipboard.writeText(text);
    if (publicLinkStatus) {
      publicLinkStatus.textContent = "Copied to the clipboard.";
    }
  } catch (error) {
    publicLinkUrl.focus();
    publicLinkUrl.select();
    if (publicLinkStatus) {
      publicLinkStatus.textContent = "Select and copy the link below.";
    }
  }
}

async function openPublicLink(story) {
  clearError(publicLinkDialog);
  setPublicLinkDialog(null, story);
  publicLinkDialog.showModal();
  try {
    let { slug } = await request(`/stories/${story.id}/public-link`);
    if (!slug && story.role === "owner") {
      ({ slug } = await request(`/stories/${story.id}/public-link`, {
        method: "POST",
      }));
    }
    setPublicLinkDialog(slug, story);
    if (slug) {
      await copyPublicLink();
    }
  } catch (error) {
    showError(publicLinkDialog, error.message);
  }
}

document.addEventListener("click", (event) => {
  const action = event.target.closest("[data-story-action]");
  if (!action) {
    return;
  }
  const row = action.closest(".story-row");
  if (!row) {
    return;
  }
  const details = row.querySelector("details");
  if (details) {
    details.open = false;
  }
  currentStory = {
    id: row.dataset.storyId,
    name: row.dataset.storyName,
    role: row.dataset.storyRole,
  };
  if (action.dataset.storyAction === "rename") {
    openRename(currentStory);
  } else if (action.dataset.storyAction === "shares") {
    openShares(currentStory);
  } else if (action.dataset.storyAction === "public-link") {
    openPublicLink(currentStory);
  }
});

if (renameForm) {
  renameForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError(renameDialog);
    const field = renameForm.querySelector('[name="name"]');
    const name = field ? field.value : "";
    try {
      await request(`/stories/${currentStory.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      const row = document.querySelector(
        `.story-row[data-story-id="${currentStory.id}"]`
      );
      if (row) {
        row.dataset.storyName = name;
        const link = row.querySelector(".story-link");
        if (link) {
          link.textContent = name;
        }
      }
      currentStory.name = name;
      renameDialog.close();
    } catch (error) {
      showError(renameDialog, error.message);
    }
  });
}

if (shareGrantForm) {
  shareGrantForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError(sharesDialog);
    const userId = Number(shareGrantForm.elements.user_id.value);
    const role = shareGrantForm.elements.role.value;
    if (!userId) {
      showError(sharesDialog, "Choose a user to share with.");
      return;
    }
    try {
      await request(`/stories/${currentStory.id}/shares`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId, role }),
      });
      shareGrantForm.reset();
      await loadShares(currentStory.id);
    } catch (error) {
      showError(sharesDialog, error.message);
    }
  });
}

if (publicLinkCopy) {
  publicLinkCopy.addEventListener("click", copyPublicLink);
}

if (publicLinkRevoke) {
  publicLinkRevoke.addEventListener("click", async () => {
    clearError(publicLinkDialog);
    try {
      await request(`/stories/${currentStory.id}/public-link`, {
        method: "DELETE",
      });
      setPublicLinkDialog(null, currentStory);
      if (publicLinkStatus) {
        publicLinkStatus.textContent = "The public link has been revoked.";
      }
    } catch (error) {
      showError(publicLinkDialog, error.message);
    }
  });
}

for (const close of document.querySelectorAll("[data-dialog-close]")) {
  close.addEventListener("click", () => {
    const dialog = close.closest("dialog");
    if (dialog) {
      dialog.close();
    }
  });
}
