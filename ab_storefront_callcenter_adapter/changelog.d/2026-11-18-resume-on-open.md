# Resume signed-in chat on opening

Current changes before commit:
- Resolve the signed-in customer's existing active website session when opening the chat launcher, including requests for a temporary thread.
- Load its existing conversation and agent replies immediately, without requiring another message to persist the thread.
- Keep website/account authorization and guest handoff checks; preserve temporary chats when no active session exists.
- Add browser coverage for a pre-existing signed-in session, compact mode, fold/reopen, previous agent replies and no duplicate sessions.
- Extend HTTP coverage to ensure open requests reuse active sessions and never restore ended sessions.

Files changed:
- controllers/chat.py
- tests/test_adapter.py
- changelog.d/2026-11-18-resume-on-open.md

Recent relevant commit:
- Commit: b0095b65
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints
- Allow website selection on new endpoints.
- Files changed: README.md, __manifest__.py, changelog.d/2026-11-17-endpoint-website-selector.md, tests/test_adapter.py, views/views.xml.

Validation:
- Existing-session browser regression failed before the controller correction and passed afterward.
- Three focused regressions passed: existing-session browser reopen, new-chat browser send/reply and HTTP retry/resume/history.
- Added HTTP open/closed-session assertions also passed in a focused rerun.
- Evidence: /tmp/native-existing-reopen-fixed.log and /tmp/native-existing-reopen-history-verified.log.
- Isolated database: storefront_chat_validation_20261117; HTTP/gevent: 5069/5072.
- Python syntax, both Arabic catalog formats and diff whitespace checks pass. No UI strings changed.
- Only the storefront Odoo Python process needs reloading to activate the controller correction; no database schema/module upgrade or gateway restart is required for this change.
