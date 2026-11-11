# Archive legacy chatter orders and detach OMS

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Reject creation, editing, deletion and transitions on legacy orders, lines and audits, including sudo callers. Preserve states and audited snapshots.
- Keep scoped historical list/form views; retain Inbox action IDs, conversation branch sharing and native Sales POS handoff.
- Remove the OMS dependency, OMS-only inherited view and obsolete editing dialogs; adapt tests and both Arabic catalogs.
- Preserve preceding CRM, contact and POS-handoff work included in this update.

Files changed:
- `__manifest__.py`
- `models/orders.py`
- `models/workspace.py`
- `security/ir.model.access.csv`
- `views/views.xml`
- `views/branch_location.xml`
- `static/src/order_dialog.js (removed)`
- `static/src/order_dialog.xml (removed)`
- `static/src/order_dialog.scss (removed)`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
