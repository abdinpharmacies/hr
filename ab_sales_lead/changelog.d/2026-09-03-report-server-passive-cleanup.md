Recent relevant commit:

- Commit: `3db5d596c9429ff082c3fe9b0466692b945f788f`
- Author: emadco88
- Date: 2026-07-28
- Original subject: INIT commit pos19
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_sales_lead/__init__.py
  - ab_sales_lead/__manifest__.py
  - ab_sales_lead/models/__init__.py
  - ab_sales_lead/models/ab_sales_lead.py
  - ab_sales_lead/security/ir.model.access.csv
  - ab_sales_lead/security/rules_sales_lead.xml
  - ab_sales_lead/static/src/pos/pos_lead.scss
  - ab_sales_lead/static/src/pos/pos_lead_patch.js
  - ab_sales_lead/static/src/pos/pos_lead_templates.xml
  - ab_sales_lead/tests/__init__.py
  - ab_sales_lead/tests/test_ab_sales_lead.py
  - ab_sales_lead/views/ab_sales_lead_views.xml
  - ab_sales_lead/views/menus.xml

Current changes before commit:

- User-facing changes:
  - Added passive sync metadata inheritance for classified high-value report facts where applicable.
  - Replaced explicit report-side user relations with `ab_users` placeholders where this module declares user fields.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_sales_lead/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_lead/__manifest__.py
  - ab_sales_lead/models/ab_sales_lead.py
