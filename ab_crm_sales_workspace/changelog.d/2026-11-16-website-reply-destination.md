# Provider-specific reply destinations

Current changes before commit:

- Add narrow composer hooks for a provider's reply method and captured destination arguments.
- Preserve the existing Telegram/WhatsApp send arguments and behavior; the Website addon is receive-only.

Files changed:

- `__manifest__.py`
- `static/src/workspace.js`
- `changelog.d/2026-11-16-website-reply-destination.md`
