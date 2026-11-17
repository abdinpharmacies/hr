# One Website conversation per customer

Current changes before commit:

- Persist customer identities by submitted normalized phone, website account, branch and company; isolate missing phones by order UUID.
- Reuse canonical conversations for orders and messages, with database uniqueness, serialized intake and Odoo request retries for lock contention.
- Associate incoming messages and historical outgoing replies with their originating order; preserve previously captured UUID destinations.
- Show one Website account per customer/source and preserve individual invoice references, snapshots and manual POS entry. Website conversations are receive-only.
- Provide administrator-only bounded reconciliation with a fingerprinted preview, oldest canonical conversations, historical aliases and saved-contact conflict review. Preserve unlink evidence, message history, audits and queued operations.
- Cover scoped identities, pagination, read positions, forged destinations, blocked replies/approvals, retries, concurrency, historical reconciliation, linked Telegram navigation and English/Arabic receive-only browser behavior.

Files changed:

- `__manifest__.py`
- `models/adapter.py`
- `security/ir.model.access.csv`
- `security/security.xml`
- `static/src/order.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/contact_group_concurrency.py`
- `tests/test_adapter.py`
- `tests/test_contact_groups.py`
- `tests/test_pos.py`
- `README.md`
- `changelog.d/2026-11-16-customer-conversations.md`
