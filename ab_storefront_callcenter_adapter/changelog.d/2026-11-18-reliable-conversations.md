# Reliable website conversations

Current changes before commit:
- Persist tab-scoped customer UUIDs and drafts across retries, reload and navigation, with bounded automatic recovery.
- Add atomic native-send deduplication, cursor history and reconnect, visibility and pageshow recovery.
- Rotate guest identity after explicit End chat, re-authorize native destinations and reject new replies to ended sessions.
- Verify guest ownership and authenticated account before handoff, revoke guest access and resume signed-in history.
- Produce version 3 lifecycle events only after the owner enables the new endpoint switch; keep checkout independent.

Files changed:
- __manifest__.py
- controllers/chat.py
- models/adapter.py
- models/chat.py
- static/src/chat.js
- static/src/native.js
- static/src/native_history.js
- static/src/native_history.xml
- security/security.xml
- security/ir.model.access.csv
- views/views.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_adapter.py
- README.md
- changelog.d/2026-11-18-reliable-conversations.md
