# Access rollback — 2026-11-17

## Recent commit

- Commit: `eda7652b65af99f01c606231fd5a44969a6f943a`
- Author: hossam elsheikh
- Date: 2026-11-12T16:35:39+02:00
- Original commit subject: ab_purchase/FIX: repair purchase forms and show invoice details

## Current changes before commit:

- Remove the later administrator-create exception and submission ACL prechecks; preserve quantity, stock, posting and duplicate safeguards.
- Access behavior restored to `82ea1dc7`; prior security-repair acceptance results are historical. No user memberships or passwords changed.

Files changed:

- `ab_purchase/models/ab_purchase_header.py`
- `ab_purchase/models/ab_purchase_je_header_delegate_common.py`
- `ab_purchase/models/ab_purchase_notice_header.py`
- `ab_purchase/models_accounting/ab_purchase__header_inherit.py`
- `ab_purchase/models_accounting/ab_purchase__notice_inherit.py`
- `ab_purchase/views/ab_purchase_header.xml`
- `ab_purchase/views/ab_purchase_notice_header.xml`
