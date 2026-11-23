# Concurrent personal chat preferences

## Recent relevant commit

- Commit: `24f4719fe2861f7076e068157e9d65cf59b25411`
- Author: Alhassan Hossny
- Date: 2026-11-23
- Original subject: `ab_crm_website/fix: preserve employee context for media uploads`
- Preserved employee context during media uploads and conversation workflows.
- Files changed: `README.md`, `__manifest__.py`, `changelog.d/2026-11-17-native-chat.md`, `changelog.d/2026-11-18-chat-lifecycle-names-startup.md`, `changelog.d/2026-11-18-composer-attachment-menu.md`, `changelog.d/2026-11-18-message-reply-menu.md`, `changelog.d/2026-11-18-order-notifications.md`, `changelog.d/2026-11-18-order-replies-media.md`, `changelog.d/2026-11-18-reliable-conversations.md`, `changelog.d/2026-11-18-website-bot-icon.md`, `changelog.d/2026-11-22-centered-icons-and-linked-chats.md`, `changelog.d/2026-11-22-chat-identity-dispatch.md`, `changelog.d/2026-11-22-inbox-archive-header.md`, `changelog.d/2026-11-22-inbox-targets-and-archive-table.md`, `changelog.d/2026-11-22-remove-chat-archive.md`, `changelog.d/2026-11-22-sales-chatter-ux.md`, `changelog.d/2026-11-22-shared-agent-chats.md`, `changelog.d/2026-11-23-two-server-qa.md`, `controllers/adapter.py`, `i18n/ar.po`, `i18n/ar_001.po`, `media_protocol.py`, `models/__init__.py`, `models/adapter.py`, `models/chat.py`, `models/media.py`, `models/targets.py`, `protocol.py`, `security/ir.model.access.csv`, `security/security.xml`, `static/src/img/abdin_bot.jpg`, `static/src/img/callcenter_support.png`, `static/src/order.scss`, `static/src/order.xml`, `static/src/reply.js`, `tests/__init__.py`, `tests/test_adapter.py`, `tests/test_chat_ux.py`, `tests/test_contact_groups.py`, `tests/test_pos.py`, `views/views.xml`.

## Current changes before commit:

- Release 19.0.1.15.1: roll back competing preference inserts in a savepoint and
  retry the complete request with a fresh snapshot using Odoo ConcurrencyError.
- Match only the personal target preference unique constraint; preserve unrelated errors.
- Cover read-position monotonicity, alert argument guards and duplicate alert acknowledgements.
- Keep existing actor, company and branch isolation and shared-login employee separation.
- Files changed: `__manifest__.py`, `models/targets.py`, `tests/test_chat_ux.py`,
  `changelog.d/2026-11-23-preference-concurrency.md`.
