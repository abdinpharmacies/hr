# Settlement PDF access

Commit: `43af83499`
Author: emadco88
Date: 2026-11-09
Original commit subject: `migrate19 INIT`

- Brought the settlement PDF action into the Odoo 19 addon.

Files changed (relevant to this fix):
- `models/ab_custody_reconciliation_header.py`

## Current changes before commit:

- Print accessible settlements without opening the administrator-only company document-layout wizard.

Files changed:
- `models/ab_custody_reconciliation_header.py`
- `changelog.d/2026-11-24-settlement-print-access.md`
