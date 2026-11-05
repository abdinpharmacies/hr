# Telegram-first Sales Operations

Current changes before commit:

- Add the Sales Operations Owl workspace beside POS, employee-bound claims, five-second inbox refresh, source-channel indicators and English/Arabic UI.
- Link central intake to existing replica/default-store records and enforce company, CRM-branch, user-store and employee-store permissions server-side.
- Match owned Telegram contacts by exact normalized phone; retain verified identities and require staff confirmation for typed/third-party numbers.
- Add channel orders, retained lines and immutable audit evidence with Draft/Accepted/Closed/Cancelled states, accepted snapshots, revisions and price-change history.
- Keep acceptance independent of sales, invoicing, payment and stock submission.
- Include focused business/security tests and deployment guidance.

Files changed:

- `__init__.py`, `__manifest__.py`
- `models/__init__.py`, `models/workspace.py`, `models/orders.py`
- `security/security_groups.xml`, `security/record_rules.xml`, `security/ir.model.access.csv`
- `views/views.xml`
- `static/src/workspace.js`, `static/src/workspace.xml`, `static/src/workspace.scss`
- `static/description/icon.png`
- `i18n/ar.po`, `i18n/ar_001.po`
- `tests/__init__.py`, `tests/test_workspace.py`
- `README.md`, `VALIDATION.md`
- `changelog.d/2026-11-04-sales-operations.md`
