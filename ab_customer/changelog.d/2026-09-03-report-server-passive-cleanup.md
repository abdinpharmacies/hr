Recent relevant commit:

- Commit: `4a9f482fa276a7945b025d197fc4c4964f327e18`
- Author: Alhassan Hossny
- Date: 2026-08-25
- Original subject: ab_customer: relax master fields for report sync
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_customer/changelog.d/2026-08-25-report-server-master-placeholders.md
  - ab_customer/models/ab_customer.py

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_customer/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_customer/models/ab_customer_contact.py
