Recent relevant commit:

- Commit: `3db5d596c9429ff082c3fe9b0466692b945f788f`
- Author: emadco88
- Date: 2026-07-28
- Original subject: INIT commit pos19
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_sales_cashier/__init__.py
  - ab_sales_cashier/__manifest__.py
  - ab_sales_cashier/models/__init__.py
  - ab_sales_cashier/models/ab_sales_cashier_api.py
  - ab_sales_cashier/models/ab_sales_cashier_close_wizard.py
  - ab_sales_cashier/security/ir.model.access.csv
  - ab_sales_cashier/static/src/cashier/cashier_action.js
  - ab_sales_cashier/static/src/cashier/cashier_action.scss
  - ab_sales_cashier/static/src/cashier/cashier_action.xml
  - ab_sales_cashier/tests/__init__.py
  - ab_sales_cashier/tests/test_cashier_api.py
  - ab_sales_cashier/views/cashier_action.xml
  - ab_sales_cashier/views/cashier_close_wizard.xml

Current changes before commit:

- User-facing changes:
  - Replaced explicit report-side user relations with `ab_users` placeholders where this module declares user fields.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_sales_cashier/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_cashier/__manifest__.py
  - ab_sales_cashier/models/ab_sales_cashier_close_wizard.py
