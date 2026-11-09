# Renderer toolchain

## Version policy

Keep Node packages in `skillRoot/package-lock.json`. Keep PlantUML and Structurizr versions in the bootstrap scripts. Do not rely on whatever happens to be installed globally. `skillRoot` is the directory containing this skill's `GUIDE.md`, not the host project's root.

## Renderer mapping

| Format | Runtime in this repository | Primary output |
|---|---|---|
| Mermaid | `skillRoot/node_modules/@mermaid-js/mermaid-cli` | SVG or PNG |
| PlantUML | `skillRoot/tools/bin/plantuml.jar` + Java | SVG, PNG, PDF |
| Structurizr DSL | `skillRoot/tools/bin/structurizr/` + Java | validated DSL and exported PlantUML views |
| D2 | `skillRoot/node_modules/@terrastruct/d2` WASM | SVG |
| Graphviz DOT | `skillRoot/node_modules/@hpcc-js/wasm-graphviz` | SVG |
| draw.io XML | `skillRoot/node_modules/drawio-headless` | SVG or PNG |

## Why D2 and Graphviz use WASM

The project does not require native `d2` or `dot` binaries. Node loads the pinned WASM packages and writes SVG files. This keeps the renderer portable and avoids platform-specific binary discovery. Native CLIs are still acceptable when a project already standardizes on them; record their versions and keep the WASM path as a fallback.

## Offline Structurizr

Structurizr's `theme default` can fetch `https://static.structurizr.com/themes/default/theme.json`. For offline or restricted-network builds, omit the remote theme unless a local theme file is provided. Run `validate` first, then `export -f plantuml`, and render the exported PlantUML locally.

## Mermaid and npx

Avoid using an unpinned `npx --yes` command in CI. The skill pins Mermaid CLI in `skillRoot/package.json`; use the local binary through `npm exec -- mmdc` or `npx --no-install mmdc` after running `npm ci` from `skillRoot`. An npx-only invocation stores packages in the user's npm cache and is not a stable skill installation.

On GitHub-hosted Linux runners, Chromium may fail with `No usable sandbox` when Mermaid CLI launches Puppeteer. The repository's CI scripts pass `scripts/puppeteer-ci.json`, which adds `--no-sandbox` and `--disable-setuid-sandbox` for the isolated CI runner. Do not make those flags the default for local browsing or untrusted multi-tenant environments.

## draw.io source and output

`.drawio` and `.xml` files are editable source, not image files. Keep them under version control. Use draw.io Desktop, diagrams.net, or `drawio-headless` to produce SVG/PNG. Review the exported image once because XML can contain valid geometry that is still visually awkward.
