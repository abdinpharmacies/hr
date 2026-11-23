# Reliable website conversations

Current changes before commit:
- Negotiate version 3 identity-binding and session-ended events while preserving existing message envelopes.
- Group verified account messages before phone matches; retain old snapshots and destination evidence.
- Freeze order/live-chat reply destinations, reject ended-session dispatch and allow manager-reviewed same-token retries.
- Add website saved replies, required-placeholder reuse, length and navigation guards, destination labels and both Arabic catalogs.

Files changed:
- __manifest__.py
- controllers/adapter.py
- models/adapter.py
- models/chat.py
- protocol.py
- static/src/reply.js
- static/src/order.xml
- views/views.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_contact_groups.py
- README.md
- changelog.d/2026-11-18-reliable-conversations.md
