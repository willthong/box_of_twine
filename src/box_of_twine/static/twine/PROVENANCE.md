# Vendored Twine editor

This directory contains the static web build of the Twine editor, served by
Box of Twine. It is vendored unmodified; see
`docs/adr/0001-fork-twinejs-with-http-persistence.md` for why we fork the
editor rather than ship it as-is.

## Upstream

- **Upstream project:** https://github.com/klembot/twinejs (`klembot/twinejs`)
- **Fork used:** https://github.com/willthong/twinejs
- **Pinned release:** tag `2.12.1`
- **Commit:** `4ebcce6a69c62b1c4b51bb76f2b7ac51dd84d9d2`
  (merge of `develop` into the `2.12.1` release)
- **License:** GPL-3.0. The upstream `LICENSE` file is copied verbatim to
  `LICENSE` in this directory.

The upstream project's `package.json` reports `"version": "2.12.1"` and
`"license": "GPL-3.0"`.

## How this build was produced

Built from source in this container with the pinned source and the upstream
`build:web` script:

```sh
git clone --depth 1 --branch 2.12.1 https://github.com/willthong/twinejs.git
npm install --ignore-scripts
npm run build:web          # tsc && vite build, plus the PWA postbuild step
```

The build output is `dist/web/`; its contents were copied to this directory.
`npm install --ignore-scripts` skips Electron's binary download, which the web
build does not need.

Fallback used only if a source build is not possible: the upstream release
asset `twine-2.12.1-web.zip` from
<https://github.com/klembot/twinejs/releases/tag/2.12.1>, which is the same
`build:web` output. The fork `willthong/twinejs` publishes no release assets.

The source build was verified against the official release asset: every file
is byte-identical except `sw.js`, whose Workbox precache list differs only in
the ordering of a few entries (filesystem traversal order). No content differs.

## Contents

- `index.html` — SPA shell.
- `assets/` — hashed JS/CSS bundles and Nunito webfonts (4 files).
- `locales/` — UI translations loaded at runtime (23 files).
- `icons/` — favicon and PWA icons.
- `sw.js`, `workbox-9c191d2f.js`, `registerSW.js`, `manifest.webmanifest` —
  PWA service worker from the stock build.
- `story-formats/` — the story formats bundled by the stock build. The four
  stock formats and their versions are:
  - **Chapbook** 1.2.3, 2.3.1
  - **Harlowe** 1.2.4, 2.1.0, 3.3.9
  - **Snowman** 1.5.0, 2.1.4
  - **SugarCube** 1.0.35, 2.37.3
  - plus **Paperthin** 1.0.0, which upstream also bundles.

Total: 60 files, about 5.0 MB (including `LICENSE`).

## Serving notes

The Vite build uses `base: './'`, so `index.html` references its assets with
**relative** URLs (`./assets/...`, `./icons/...`, `./registerSW.js`). At
runtime the story formats are fetched by URL as well, using the hardcoded
relative paths in `src/store/story-formats/defaults.ts`
(`story-formats/<name>-<version>/format.js`), and locales load from
`locales/<code>.json`. All of these resolve against the document's base URL.

Consequences for serving the SPA at `/edit/<story_id>`:

- If `index.html` is returned for `/edit/<story_id>`, the browser resolves
  those relative URLs against `/edit/` and requests e.g.
  `/edit/assets/index-BhufTn3L.js`, not `/static/twine/assets/...`.
- Serving the shell with an injected `<base href="/static/twine/">` makes
  every relative URL, including the runtime story-format and locale loads,
  resolve under Flask's static mount. This is the simplest fix.
- Because the SPA uses a `HashRouter` (client routes live after `#`), the
  server only has to return this shell; it does not need routes for the
  client-side paths.

The PWA service worker is part of the stock build. Its scope follows the
document base URL; if it becomes a caching problem for the editor, removing
`registerSW.js`/`sw.js` or serving the shell without registering it is safe.
