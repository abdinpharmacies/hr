Recent relevant commit:

- Commit: `13b0285c5faa88562ad0551372e3393f2a478470`
- Author: Mohamed Fawzy
- Date: 2026-08-09
- Original subject: ab_transfer/fix:   Store_Trans_h.stnh_notes = 4   Odoo Transfer: Transfer 123 to be in same line
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_transfer/models/ab_transfer_header.py
  - ab_transfer/tests/test_transfer_type_notes.py

Current changes before commit:

- User-facing changes:
  - Added passive sync metadata inheritance for classified high-value report facts where applicable.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_transfer/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_transfer/__manifest__.py
  - ab_transfer/models/ab_transfer_header.py
  - ab_transfer/models/ab_transfer_line.py
  - ab_transfer/models/ab_transfer_receive.py
  - ab_transfer/models/ab_transfer_request.py
