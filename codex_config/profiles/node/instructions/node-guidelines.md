# NODE.JS GUIDELINES

## Language & Runtime

- TypeScript-first for new projects; use plain ESM JavaScript only when a project is already CommonJS-based and unmodified.
- Use modern ESM (`import`/`export`) syntax. Use `node:` import specifiers for Node core modules.
- Target the project's declared Node runtime; do not use APIs that postdate it without noting a version bump.

## Project Structure

- Keep entry points minimal; put logic in `src/`. Separate pure logic from framework/data-layer concerns.
- Prefer small, single-responsibility modules over large barrel files.

## Dependencies & Versions

- Never guess package versions. Before adding a package, perform a live web search to retrieve the absolute latest stable version.
- Pin exact versions in `package.json` or use a lockfile; do not leave floating `^` major ranges for critical dependencies.
- Avoid adding a dependency when platform or modern built-ins suffice.

## Code Quality

- Clean code: single responsibility principle and DRY.
- Use clear, descriptive, accurate naming.
- Handle async errors explicitly; do not swallow rejected promises.

## Comments Rule

- Do NOT add comments to code unless the user explicitly asks.
