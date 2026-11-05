# Sales Chatter development pilot

Current changes before commit:

- Preserve the workspace menu/action IDs and place Sales Chatter immediately after POS.
- Add server-side contact search and cursor pagination for conversations and message history.
- Preserve unsent conversation/order drafts when switching streams and preserve scroll position during refresh.
- Show employee assignment, contacted-stream navigation, timestamps and durable delivery states.
- Match the WhatsApp dashboard panel/bubble styling within workspace-only selectors; keep deferred streams read-only for sending.
- Enforce claimed employee ownership for direct message create/edit/approve/retry and protect Telegram customer linking.
- Provide an explicitly loaded, disabled development service user in module-owned security XML.
- Translate added strings in both Arabic catalogs and verify RTL rendering.

Files changed:

- `__manifest__.py`, `views/views.xml`
- `models/workspace.py`
- `static/src/workspace.js`, `static/src/workspace.xml`, `static/src/workspace.scss`
- `i18n/ar.po`, `i18n/ar_001.po`
- `tests/test_workspace.py`
- `security/telegram_development_user.xml`
- `README.md`, `VALIDATION.md`
- `changelog.d/2026-11-04-sales-chatter.md`
