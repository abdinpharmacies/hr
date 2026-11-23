# Website chat lifecycle, names and visibility

Current changes before commit:
- Open this website adapter's livechat windows through saved compact mode, including the temporary-to-persisted session swap.
- Include the authenticated website account's saved customer name in chat and identity-handoff events; never accept it from browser parameters.
- Add a signed-in browser regression with compact mode, customer send, agent reply and reopening; verify the captured name.
- Preserve guest ownership, ended-session rejection, retries and history recovery.

Files changed:
- models/chat.py
- static/src/native.js
- tests/test_adapter.py
- changelog.d/2026-11-18-chat-lifecycle-names-visibility.md

Recent relevant commit:
- Commit: b0095b65
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints
- Allow website selection when creating endpoints.
- Files changed: README.md, __manifest__.py, changelog.d/2026-11-17-endpoint-website-selector.md, tests/test_adapter.py, views/views.xml.

Validation:
- Five focused tests passed with zero failures/errors/skips on storefront_chat_validation_20261117, HTTP/gevent 5069/5072.
- Evidence: /tmp/storefront-chat-final-validation.log.
- The compact-mode browser regression failed before the window override and passed after it.
- Both Arabic catalogs pass gettext format checks; no new source UI strings.
- Live default-website endpoint lifecycle delivery enabled through ORM. Existing ended visitor recovery uses the lifecycle queue, service receiver and acknowledgement APIs.
- Running Odoo processes and the gateway were not restarted. Reload the updated receiver before the producer; reload the gateway for automatic lifecycle delivery.
