# Accounting changes

## Current changes before commit:

- Allow accounting account and allowed-field authorization records to retain an empty authorization group during the Odoo 15 to 19 migration.
- Keep each group relation, index, and uniqueness constraint; do not assign replacement permissions.
- Keep the account and allowed-field references required and retain existing permission defaults.

Files changed:
- `models/user_uth.py`
- `changelog.d`

## 43af83499 — emadco88 — 2026-11-09

Original commit subject: `migrate19 INIT`

- Initialize the Odoo 19 accounting addon, including account authorization models.

Files changed (relevant to this update):
- `models/user_uth.py`
