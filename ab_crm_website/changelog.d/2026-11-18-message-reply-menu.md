# Website message reply menu

Current changes before commit:
- Use the Sales Chatter message menu → Reply action for website messages, matching WhatsApp and Telegram.
- Remove the duplicate website reply arrow and retain the shared quoted preview and cancel action.
- Extend English desktop and Arabic mobile browser coverage for menu selection, cancellation, reselection and delivery to the selected website order.
- Preserve the existing uncommitted website composer, media and conversation work.

Files changed:
- static/src/order.xml
- tests/test_contact_groups.py
- changelog.d/2026-11-18-message-reply-menu.md

Recent relevant commit:
- Commit: 149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: ab_crm_website/feat: group orders into receive-only customer conversations
- Grouped website orders under customer conversations and introduced website-specific chatter presentation.
- Files changed: README.md, __manifest__.py, changelog.d/2026-11-16-customer-conversations.md, changelog.d/2026-11-16-link-candidate-locks.md, changelog.d/2026-11-16-receive-only.md, i18n/ar.po, i18n/ar_001.po, models/adapter.py, security/ir.model.access.csv, static/src/order.xml, tests/contact_group_concurrency.py, tests/test_adapter.py, tests/test_contact_groups.py, tests/test_pos.py.

Validation:
- English desktop and Arabic mobile browser checks cover the standard reply menu, quoted preview, cancel/reselect, attachments, saved replies and selected-order routing.
- Receive-only English and Arabic browser checks preserve disabled reply behavior.
- Isolated database: website_chat_validation_20261117; HTTP/gevent ports: 5069/5072.
- Evidence: /tmp/website-reply-menu-acceptance-tests.log.
- XML/Python syntax, both Arabic catalog format checks and git diff whitespace checks pass.
- No new source UI strings; the existing translated Reply and Cancel reply controls are reused.
