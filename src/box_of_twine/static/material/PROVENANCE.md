# Vendored Material Web

The Material 3 components used by the server-rendered wrapper pages (login,
home, admin users) are from **`@material/web` 2.5.0**, bundled for the browser.

- Upstream: <https://github.com/material-components/material-web>
- Package: `@material/web@2.5.0`
- License: Apache-2.0 (see `LICENSE` in this directory)

`material.js` is an ES-module bundle produced with esbuild from this entry:

```js
import '@material/web/button/filled-button.js';
import '@material/web/button/outlined-button.js';
import '@material/web/button/text-button.js';
import '@material/web/textfield/outlined-text-field.js';
import '@material/web/checkbox/checkbox.js';
import '@material/web/list/list.js';
import '@material/web/list/list-item.js';
import '@material/web/divider/divider.js';
```

Command:

```sh
npm install @material/web@2.5.0 esbuild
npx esbuild entry.js --bundle --format=esm --minify --outfile=material.js
```

The bundle is committed so the runtime image needs no Node toolchain. Theme
colour tokens live in `templates/theme.css` (inlined by `base.html`).
