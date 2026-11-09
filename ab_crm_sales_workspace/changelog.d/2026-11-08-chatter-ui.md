# Chatter templates, actions and navigation

Current changes before commit:
- Version 19.0.1.10.0 adds searchable saved replies, guarded unsaved edits, stable save/refresh selection and archive clearing.
- Adds twelve composer emojis with caret restoration, and a shared pointer/keyboard/chevron menu with native-menu exceptions and eligible retry.
- Adds employee-scoped unread metadata, a stable first-unread marker, latest navigation and conversation search with query-aware pagination and stale-response guards.
- Adds lazy private image thumbnails, media sizes, file actions and object URL cleanup without new public routes.
- Preserves server permissions, immutable history, retry identity, channel drafts and existing attachment limits; adds English/Arabic catalogs and isolated regressions.

Files changed:
- `__manifest__.py`
- `models/saved_reply.py`
- `models/workspace.py`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/src/message.js`
- `static/src/message.xml`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/src/workspace.scss`
- `static/tests/chatter_ui.test.js`
- `static/tests/message.test.js`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `README.md`
- `VALIDATION.md`
- `changelog.d/2026-11-08-chatter-ui.md`
