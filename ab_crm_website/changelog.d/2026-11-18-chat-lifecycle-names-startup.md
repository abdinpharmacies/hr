# Website chat lifecycle, customer names and startup repair

Current changes before commit:
- Accept the optional, bounded customer name supplied by the authenticated website integration and display it in Sales Chatter.
- Preserve saved names when older queued messages omit name metadata; support name updates during verified guest-to-account handoff.
- Close a guest conversation after its final visitor session ends, preserving other active sessions and signed-in customer history.
- Reject messages from ended sessions; reopen the visitor conversation only for a new session.
- Show the translated ended-chat notice and remove the reply composer when no destination remains.
- Repair the retry view's inline arch formatting for Odoo XML development mode, preserving its XML ID and manager-only action.
- Extend business, security, English desktop and Arabic mobile regressions.

Files changed:
- models/adapter.py
- protocol.py
- static/src/order.xml
- views/views.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_contact_groups.py
- changelog.d/2026-11-18-chat-lifecycle-names-startup.md

Recent relevant commit:
- Commit: 149fb44e
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: ab_crm_website/feat: group orders into receive-only customer conversations
- Group website orders by customer and preserve website-specific timelines.
- Files changed: README.md, __manifest__.py, changelog.d/2026-11-16-customer-conversations.md, changelog.d/2026-11-16-link-candidate-locks.md, changelog.d/2026-11-16-receive-only.md, i18n/ar.po, i18n/ar_001.po, models/adapter.py, security/ir.model.access.csv, static/src/order.xml, tests/contact_group_concurrency.py, tests/test_adapter.py, tests/test_contact_groups.py, tests/test_pos.py.

Validation:
- Five business/security tests passed: visitor closure and reopening, customer names and legacy messages, handoff and frozen destinations, cross-branch/company isolation, forgery rejection.
- Two browser tests passed: English desktop and Arabic mobile, including translated ended status, disabled composer and preserved order replies.
- Isolated database: website_chat_validation_20261117; HTTP/gevent: 5075/5076; targeted upgrade with --dev=xml.
- Evidence: /tmp/callcenter-chat-business-verified.log and /tmp/callcenter-chat-ui-verified.log.
- Exported /tmp/callcenter-chat-lifecycle.pot; merged only the ended-notice JavaScript reference into both existing Arabic catalogs.
- Python/XML syntax, catalog formats and diff whitespace checks pass.
- Enabled lifecycle delivery on the live website endpoint through ORM. Recovered and acknowledged one previously-ended guest event through the normal service receiver; verified its callcenter conversation is closed.
- Live Python services were not restarted. Reload callcenter Odoo before storefront Odoo, then reload the gateway to activate the updated lifecycle consumer and producer automatically.
