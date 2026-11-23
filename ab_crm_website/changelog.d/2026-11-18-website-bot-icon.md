# Website conversation bot icon

Current changes before commit:
- Display the supplied Abdin bot image in website channel indicators in the inbox and conversation header.
- Hide the Floating chat origin label from messages; preserve Order chat labels and invoice presentation.
- Keep the existing accessible website channel names and unread indicators.
- Extend English desktop and Arabic mobile browser scenarios to check image loading, square icon dimensions, hidden globe glyphs, floating labels and order labels.

Files changed:
- static/src/img/abdin_bot.jpg
- static/src/order.scss
- static/src/order.xml
- tests/test_contact_groups.py
- changelog.d/2026-11-18-website-bot-icon.md

Recent relevant commit:
- Commit: 149fb44e
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: ab_crm_website/feat: group orders into receive-only customer conversations
- Grouped website orders by customer and introduced website chatter presentation.
- Files changed: README.md, __manifest__.py, changelog.d/2026-11-16-customer-conversations.md, changelog.d/2026-11-16-link-candidate-locks.md, changelog.d/2026-11-16-receive-only.md, i18n/ar.po, i18n/ar_001.po, models/adapter.py, security/ir.model.access.csv, static/src/order.xml, tests/contact_group_concurrency.py, tests/test_adapter.py, tests/test_contact_groups.py, tests/test_pos.py.

Validation:
- Two browser tests passed, zero failures/errors/skips: English desktop and Arabic mobile, including floating-label visibility and preserved order labels.
- Isolated DB: website_chat_validation_20261117; HTTP/gevent ports: 5069/5072.
- Log: /tmp/website-bot-icon-acceptance.log.
- Python/XML syntax, SCSS compilation, both Arabic catalog format checks and diff whitespace checks passed.
- Supplied image copied byte-for-byte; no new UI strings or catalog changes required.
- Live service was not upgraded or restarted.
