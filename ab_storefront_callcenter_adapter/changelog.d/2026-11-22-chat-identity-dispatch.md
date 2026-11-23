# Website chat identity and terminal lifecycle

Recent relevant commit:

- Commit: `b0095b6521105f026f3de12e4283d402255f28c3`
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: `ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints`
- Change: Allow website selection when creating an endpoint.
- Files changed: `__manifest__.py`, `README.md`, `views/views.xml`, `tests/test_adapter.py`, `changelog.d/2026-11-17-endpoint-website-selector.md`.

Current changes before commit:

- Add verified account-partner name and bounded phone metadata to customer chat and login handoff; retain account UUID ownership and legacy compatibility.
- Close only the dispatched order, preserve history and accepted-send acknowledgements, and reject new direct chatter posts, messages and uploads.
- Publish an idempotent order-dispatch lifecycle event only after the destination's accepted messages are acknowledged; preserve guest end ordering too.
- Keep dispatch notification activation off until the receiver is upgraded, preserve the initial order acknowledgement readiness gate, and retain terminal closure after status reversal.
- Use the existing Abdin bot avatar for the module-owned bridge user. Poll order closure/readiness in the module-scoped portal chatter and show the correct translated closure reason once.
- Maintain both Arabic catalogs and add direct-access, ordinary warehouse-user, stock-preservation, per-order isolation, replay and lifecycle-ordering regression checks.
- Preserve text entered before the standalone order-chat assets initialize, including its draft cache.
- Retry native chat initialization through Odoo transaction retries when the gateway briefly holds the endpoint lock; validate the website before acquiring that lock.
- Preserve the pre-existing uncommitted checkout, native chat, media and reliability work documented in the earlier change records.

Files changed:

- `__manifest__.py`
- `README.md`
- `models/__init__.py`
- `models/adapter.py`
- `models/chat.py`
- `models/lifecycle.py`
- `controllers/chat.py`
- `controllers/media.py`
- `security/security.xml`
- `static/src/chat.js`
- `static/src/native_history.js`
- `static/src/portal_refresh.js`
- `static/src/portal_refresh.xml`
- `views/views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_adapter.py`
- `changelog.d/2026-11-22-chat-identity-dispatch.md`
