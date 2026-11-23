# Chat exchange and bridge health

## Recent relevant commit

- Commit: `e65eab7762a0a38294eddb29c0239ec109970f9a`
- Author: Alhassan Hossny
- Date: 2026-11-23
- Original subject: `ab_storefront_callcenter_adapter/fix: keep order chatter available without acknowledgement`
- Kept native order chatter available while notification delivery is offline.
- Files changed: `README.md`, `__manifest__.py`, `controllers/chat.py`,
  `models/adapter.py`, `models/chat.py`, `models/media.py`, `static/src/chat.js`,
  `tests/test_adapter.py`, `views/views.xml`,
  `changelog.d/2026-11-23-offline-chatter-endpoint-access.md`.

## Current changes before commit:

- Release 19.0.1.5.3: authenticate delivery independently of bridge operator health.
- Keep full bridge validation for configuration, new replies/media and operator selection.
- Preserve exact accepted reply/media receipts after a later bridge fault.
- Cover inactive/missing-member bridges, delivery acknowledgements and media replay conflicts.
- Preserve endpoint cutoff, source/company ownership and offline native chatter.
- Files changed: `__manifest__.py`, `models/adapter.py`, `models/chat.py`,
  `controllers/media.py`, `tests/test_adapter.py`,
  `changelog.d/2026-11-23-bridge-delivery-isolation.md`.
