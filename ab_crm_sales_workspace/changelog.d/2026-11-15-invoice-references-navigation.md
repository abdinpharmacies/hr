# Invoice references and CRM / OMS navigation

Current changes before commit:

- Open the existing branch CSV import popup beside New without selecting records; retain native import/export and all validation and review safeguards.
- Deactivate separate import and legacy archive navigation while preserving records, security, actions and XML IDs.
- Correct retained archive view formatting for direct XML developer-mode loading; add English/Arabic import-button references.

Files changed:

- `views/branch_location.xml`
- `views/views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_workspace.py`
- `README.md`
- `changelog.d/2026-11-15-invoice-references-navigation.md`
