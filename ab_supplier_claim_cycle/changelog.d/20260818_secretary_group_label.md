# Recent Changes

## 5e5362c - Mohamed Fawzy - 2026-07-20 - ab_supplier_claim_cycle/add group system

- Added system-group implication for supplier claim administrators.

Files changed:
- `security/groups.xml`

## 4d85eab1 - Mohamed Fawzy - 2026-08-18 - ab_supplier_claim(1970#)/fix: change Supplier Claim User to be Supplier Claim Secretary and fix reviewer bug

- Renamed the supplier claim user group display label to `Supplier Claim Secretary`.
- Updated Arabic translations for the renamed secretary group label.

Files changed:
- `security/groups.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`

## Current changes before commit:

- Restored the missing Supplier Claim Cycle runtime package from `origin/main` so the installed module can load and upgrade on Odoo 19.

Files changed:
- `ab_supplier_claim_cycle/`
