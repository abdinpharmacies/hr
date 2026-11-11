# Unified contacts and open reception

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Add normalized contact phone lists, explicit customer confirmation, primary/archive actions and protected audited associations.
- Match all active numbers; retain unlinked Telegram evidence and require explicit first association.
- Add fingerprinted manager consolidation with canonical references while preserving message and order identities.
- Group channel navigation, persist selected conversations and require explicit phone selection for new orders with phone lists.
- Extend English/Arabic controls and security, concurrency, regression and browser coverage.
- Preserve the existing saved-contact, media, reaction and dispatch-related workspace improvements.

Validation and rollout: `docs/unified-contacts-rollout.md`. Live rollout completed during the user-managed maintenance window; verification and remaining unmatched historical status evidence are recorded in the rollout document.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `changelog.d/2026-11-10-unified-contacts.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/alerts.py`
- `models/contact_phones.py`
- `models/customer_streams.py`
- `models/directory.py`
- `models/orders.py`
- `models/workspace.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/order_dialog.js`
- `static/src/order_dialog.xml`
- `static/src/templates.js`
- `static/src/workspace.js`
- `static/src/workspace.scss`
- `static/src/workspace.xml`
- `static/tests/contact_phones.test.js`
- `tests/contact_concurrency.py`
- `tests/test_workspace.py`
