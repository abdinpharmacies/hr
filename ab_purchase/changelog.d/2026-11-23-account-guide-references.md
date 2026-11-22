# Purchase accounting catalog references — 2026-11-23

## Recent commit

- Commit: `39642eb5fee99e26b6ff795991677edc684d9692`
- Author: Hossam Elsheikh
- Date: 2026-11-18T15:56:12+02:00
- Original commit subject: ab_purchase: combine access settings
- Combined the existing purchase roles under one access setting.

Files changed:

- `ab_purchase/changelog.d/2026-11-18-purchase-privilege.md`
- `ab_purchase/security/security_groups.xml`

## Current changes before commit:

- Use the account catalog owned by `ab_accounting_base` for supplier, inventory, and VAT lookups, including the commented report example (20 references).
- Fix the missing supplier account XML-ID lookup during purchase claim view validation and remove the same legacy lookup dependency from related purchase workflows and reports.
- Preserve the automatic journal-entry document type reference in `ab_accounting`.
- No user-facing strings changed; Arabic and English translations require no updates.

Files changed:

- `ab_purchase/models/ab_purchase_je_header_delegate_common.py`
- `ab_purchase/models/ab_purchase_notice_header.py`
- `ab_purchase/models_accounting/ab_accounting_je_inherit.py`
- `ab_purchase/models_accounting/ab_purchase__header_inherit.py`
- `ab_purchase/models_accounting/ab_purchase__notice_inherit.py`
- `ab_purchase/models_accounting/ab_purchase_claim.py`
- `ab_purchase/models_accounting/ab_purchase_report_wizard.py`
- `ab_purchase/changelog.d/2026-11-23-account-guide-references.md`

## Verification

- Python syntax checked for all seven modified Python files.
- All 20 replacement references resolve to IDs declared in the account catalog XML data; no legacy account-guide references remain in purchase code.
- Automatic journal-entry document type reference remains unchanged.
- Runtime installation and claim-form validation remain pending: no disposable development database was identified, and the local default PostgreSQL connection failed because role `sohag151` does not exist.
