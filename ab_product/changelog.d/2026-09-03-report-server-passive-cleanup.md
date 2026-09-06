Recent relevant commit:

- Commit: `2323df242ecba3d69a405610772fa04415968bd5`
- Author: emadco88
- Date: 2026-08-24
- Original subject: ab_product/ UPD for report demo
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_product/__manifest__.py
  - ab_product/models/ab_product.py
  - ab_product/models/ab_product_barcode_temp.py
  - ab_product/models/ab_product_management_field_rule.py
  - ab_product/models/ab_product_qty.py
  - ab_product/security/ir.model.access.csv
  - ab_product/views/menus.xml

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_product/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_product/models/ab_product_management_field_rule.py
