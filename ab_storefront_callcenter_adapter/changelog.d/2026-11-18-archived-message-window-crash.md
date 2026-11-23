# Fix archived agent history destroying the chat window

Current changes before commit:
- Pass each archived message's original thread to Odoo's Message component in Previous conversations.
- Prevent shouldDisplayAuthorName from accessing a missing thread and destroying the entire livechat Owl application.
- Extend the signed-in session regression with a closed earlier conversation containing an agent reply, expand its history, and verify the current composer remains mounted.
- Preserve read-only archive rendering, ownership checks and current-session message handling.

Files changed:
- static/src/native_history.xml
- tests/test_adapter.py
- changelog.d/2026-11-18-archived-message-window-crash.md

Recent relevant commit:
- Commit: b0095b65
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints
- Allow website selection on new endpoints.
- Files changed: README.md, __manifest__.py, changelog.d/2026-11-17-endpoint-website-selector.md, tests/test_adapter.py, views/views.xml.

Validation:
- Reproduced with Playwright using the authorized signed-in account on http://127.0.0.1:4102/: session/history requests returned HTTP 200, while an archived non-self message caused an Owl lifecycle error in Message.shouldDisplayAuthorName (missing thread.channel_type).
- Verified the corrected normal frontend bundle on the actual local website: active window/composer visible, archive expanded, fold/reopen, shop navigation and mobile 390x844 all work with zero browser errors.
- Privacy-masked screenshots: /tmp/floating-chat-fixed-desktop.png and /tmp/floating-chat-fixed-mobile.png. No credentials or account data stored in repository artifacts.
- Matching isolated regression failed before correction and passed afterward. Three focused tests passed with zero failures/errors/skips: existing history/reopen, new send/reply, and retry/history ownership.
- Logs: /tmp/native-archived-agent-repro.log and /tmp/native-archived-agent-fixed.log.
- Isolated DB: storefront_chat_validation_20261117; HTTP/gevent: 5069/5072.
- XML/Python syntax, both Arabic catalog formats and diff whitespace checks pass. No UI strings changed.
- Frontend bundle refreshed on the running local website; no Odoo or gateway restart was required.
