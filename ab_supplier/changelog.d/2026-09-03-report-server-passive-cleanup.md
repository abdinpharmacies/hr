Recent relevant commit:

- Commit: `c1efa75cced28524371f36d502bfe9838cabb001`
- Author: Alhassan Hossny
- Date: 2026-08-25
- Original subject: ab_supplier: relax master fields for report sync
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_supplier/changelog.d/2026-08-25-report-server-master-placeholders.md
  - ab_supplier/models/ab_supplier.py

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_supplier/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_supplier/models/ab_supplier_bracket.py
  - ab_supplier/models/ab_supplier_discount.py
