# Native order chatter without remote acknowledgement

## eba33c7e0b1dc818212f29f501a1234633c748ed

Author: Alhassan Hossny
Date: 2026-11-23
Original commit subject: ab_storefront_callcenter_adapter/fix: preserve chat submissions during history polling

- Preserve a customer submission and its newer draft while order history refreshes.

## Current changes before commit:

- Keep native order chatter available without remote acknowledgement or an enabled chat bridge; preserve customer ownership and dispatch closure.
- Queue forwarded customer messages and private media locally, then export them and lifecycle events after initial order receipt.
- Bump the adapter to 19.0.1.5.2 and document notification-only setup.
- Validate capture, identity, direct access, browser chatter and recovery using an isolated database; see qa/two_server/NOTIFICATION_ONLY.md for current evidence.

Files changed:
- __manifest__.py
- README.md
- controllers/chat.py
- models/adapter.py
- models/chat.py
- models/media.py
- static/src/chat.js
- tests/test_adapter.py
- views/views.xml
- changelog.d/2026-11-23-offline-chatter-endpoint-access.md
