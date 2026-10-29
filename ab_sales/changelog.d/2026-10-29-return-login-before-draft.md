## 5d43ee51c06bc961579266638a2e400633221bbb - Hossam Elsheikh - 2026-10-28

Original commit subject: ab_sales/Bill Wizard as the only return entry point

- Route sales returns through the Bill Wizard and keep standard return views read-only.
- Preserve return drafts after a submission attempt and refresh the Bill Wizard after closing the popup.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-28-bill-wizard-return-only.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/pos/return_form_buttons.xml (removed)
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.xml
- ab_sales/views/ab_sales_return.xml
- ab_sales/views/ab_sales_return_line.xml
- ab_sales/views/sales_header.xml

## Current changes before commit:

- Open the employee login popup from Bill Wizard before creating a sales return draft.
- Pass the selected sale ID to the popup and defer return creation until authorized login completes.
- Mark return popup closure before asynchronous cleanup and allow cleanup of an identified draft whose details have not loaded yet. Preserve cleanup protection after a Commit attempt.
- Bump the module version to 19.0.4.1.21.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/models/ab_sales_return_ui_api.py
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js
- ab_sales/changelog.d/2026-10-29-return-login-before-draft.md
