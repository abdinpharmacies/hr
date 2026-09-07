Recent relevant commit:

- Commit: `e9d9bb6d37be9d5f9b6b4e51b9dccaecb5c9d1d7`
- Author: Alhassan Hossny
- Date: 2026-08-25
- Original subject: ab_sales_doctor: relax doctor master fields for report sync
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_sales_doctor/changelog.d/2026-08-25-report-server-master-placeholders.md
  - ab_sales_doctor/models/ab_doctor.py

Current changes before commit:

- User-facing changes:
  - Added the shared passive mirror mixin to `ab_product_doctor_prescription` because it is now classified as a high-value passive model.
  - Declared the required `ab_odoo_sync` dependency for that mixin.
- Files changed:
  - ab_sales_doctor/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_doctor/__manifest__.py
  - ab_sales_doctor/models/ab_product_doctor_prescription.py
