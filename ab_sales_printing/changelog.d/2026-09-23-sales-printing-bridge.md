# Sales printing bridge

Reference commit: `844c3d127b801b27a1162616ac374c1bf701bd64`
- Author: hager yasser
- Date: 2026-09-20
- Original subject: `ab_sales/feat(#2289): add direct A4 CUPS printing from printer button`
- Restore its bill-wizard printing behavior in a separately installable bridge.
- No prior commits exist for this new module.

Current changes before commit:
- Author: hagerYasser
- Date: 2026-09-23
- Connect the existing Sales bill wizard to shared CUPS printing through a module-owned action subclass, dialog and inherited API methods.
- Keep dependency direction in the bridge: it depends on Sales and Printing; neither existing module is changed.
- Preserve sales/return receipt rendering, A4 and POS 80mm formats, preview and browser System dialog printing.
- Refresh queues by name, require a new selection when a selected queue disappears, and reject removed queues on submission.
- Store queue and format preferences per database/user in the browser; storage failures do not block printing.
- Capture the selected receipt before opening the dialog, guard duplicate clicks and keep the dialog open after submission failure.
- Enforce existing ACLs, record rules and optional sales-prevention guards for direct printing, preview and browser printing.
- Reuse existing model security; no new models, groups, ACL grants, hooks, migrations or printer records are introduced.
- Add English source strings and Arabic translations for both `ar` and `ar_001`, using the Odoo-exported POT references.

Files changed:
- `__init__.py`
- `__manifest__.py`
- `models/__init__.py`
- `models/ab_sales_ui_api.py`
- `static/src/bill_wizard/bill_wizard_action.js`
- `static/src/bill_wizard/cups_print_dialog.js`
- `static/src/bill_wizard/cups_print_dialog.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-09-23-sales-printing-bridge.md`

Validation:
- Installed Sales without Printing/bridge in isolated database `codex_sales_printing_20260923`, then installed the bridge successfully.
- Installed Printing without Sales/bridge in isolated database `codex_printing_only_20260923`.
- Targeted bridge upgrade passed after enabling `ar_001`, which the existing Sales receipt renderer requires.
- Six rollback-only ORM scenarios passed: real sales/return QWeb rendering in both formats; invalid/empty/missing receipt and queue rejection; read-only queue discovery; sales-prevention guards; public-user denial; and own-branch allowance/cross-branch denial under test record rules.
- All printer commands were blocked during ORM tests and final submission was mocked. No physical print jobs were submitted.
- Eleven JavaScript scenarios passed for action isolation, name-based selection, preference isolation, refresh/removal, duplicate-click protection, CUPS success/failure, browser print/preview, popup/render failures, unavailable storage, stale queues and dialog receipt capture.
- Odoo asset transformation/minification, asset ordering, XML bundle generation and unique inheritance anchors passed.
- All 19 POT entries are translated in both PO files; `msgfmt --check-format` passed. Runtime Arabic dialog text and backend errors differ from English.
- Python/XML syntax, manifest developer and dependency-direction checks passed. Existing Sales and Printing files have no diff.
- Validation scripts, exported POT and logs are retained outside the runtime addon under `/tmp/ab_sales_printing_validation/`.

Deployment:
- Install `ab_sales_printing` explicitly and reload the web client; `auto_install` is disabled.
- Existing Sales receipt rendering requires the `ar_001` language to be active.
- CUPS connectivity and physical printer output remain deployment checks; integration validation used mocked submission.
