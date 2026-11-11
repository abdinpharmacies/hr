# Inbox contacts and POS handoff

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Replace the Orders frontend with Inbox, Create order and the existing POS Invoices action; retain action IDs and historical OMS records. Exclude the legacy order dialog assets while preserving pre-existing source edits.
- Keep CRM-only contact saving independent of branch connectivity. Separate saved-contact and POS-customer search results; use the existing branch lookup only on request. Require explicit selection, including formerly automatic single catalog matches.
- Display computed Is POS customer and audit explicit CRM relationship changes without changing the customer master.
- Add a CRM-only subclass of the registered POS action. Preserve native employee authentication, branch selection, capacity checks, customer lookup/creation, invoice submission and draft storage.
- Validate both sessions, employee, contact, conversation, phone, location and branch/company scope; reserve each handoff for one native draft. Carry national phone and editable delivery details once and retry CRM synchronization independently.
- Restore Inbox selection, preserve existing drafts, update English/Arabic strings and add server, component and full application tests.
- Preserve the checkout's pre-existing messaging, phone, session and contact work. No changes to ab_sales, ab_customer, Bill Wizard or employee-access source.

Validation and activation: `docs/sales-chatter-pos-handoff-validation.md`.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-10-inbox-pos-handoff.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/pos_handoff.py`
- `models/workspace.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/location.js`
- `static/src/location.xml`
- `static/src/pos_handoff.js`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/location.test.js`
- `static/tests/pos_handoff.test.js`
- `tests/__init__.py`
- `tests/test_pos_handoff.py`
- `tests/test_pos_runtime.py`
- `tests/test_workspace.py`
- `views/views.xml`
