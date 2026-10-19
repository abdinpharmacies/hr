Current changes before commit:

- Add branch-specific drawer, treasury, clearing, revenue, inventory and difference account mappings.
- Show balances from posted branch journal lines and retain immutable, idempotent source links.
- Enforce Accounting Manager setup, account authorization, branch/company isolation and both Arabic catalogs.

Validation: Targeted install/upgrade on rip_bconnect; 38 full-cycle rollback checks, 31 accounting access/bilingual view checks, and 6 Playwright checks passed. After explicit permission approval, all 38 live-cycle checks passed and 14 retained balanced journals, branch stock and waiting openings were independently verified; see scripts/stock_integration_validation/CASH_ACCOUNTING_REPORT.md.

Files changed:

- ab_accounting_cash/README.md
- ab_accounting_cash/__init__.py
- ab_accounting_cash/__manifest__.py
- ab_accounting_cash/changelog.d
- ab_accounting_cash/i18n/ar.po
- ab_accounting_cash/i18n/ar_001.po
- ab_accounting_cash/models/__init__.py
- ab_accounting_cash/models/cash_accounting.py
- ab_accounting_cash/security/ir.model.access.csv
- ab_accounting_cash/security/record_rules.xml
- ab_accounting_cash/views/cash_accounting.xml
