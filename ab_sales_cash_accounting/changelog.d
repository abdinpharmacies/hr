Current changes before commit:

- Post shift batches, treasury transfers and approved discrepancies through the native Accounting engine.
- Keep carry-forward cash in the drawer without duplicating receipts; preserve separate noncash accounts.
- Move financial configuration and review navigation under Accounting while keeping POS operations in Sales.
- Guard unresolved tax, bonus and invoice-discount valuation cases; leave historical opening valuation explicit.
- Provide the dedicated integration role and both Arabic catalogs.

Validation: Targeted install/upgrade on rip_bconnect; 38 full-cycle rollback checks, 31 accounting access/bilingual view checks, and 6 Playwright checks passed. After explicit permission approval, all 38 live-cycle checks passed and 14 retained balanced journals, branch stock and waiting openings were independently verified; see scripts/stock_integration_validation/CASH_ACCOUNTING_REPORT.md.

Files changed:

- ab_sales_cash_accounting/README.md
- ab_sales_cash_accounting/__init__.py
- ab_sales_cash_accounting/__manifest__.py
- ab_sales_cash_accounting/changelog.d
- ab_sales_cash_accounting/i18n/ar.po
- ab_sales_cash_accounting/i18n/ar_001.po
- ab_sales_cash_accounting/models/__init__.py
- ab_sales_cash_accounting/models/cash_bridge.py
- ab_sales_cash_accounting/security/groups.xml
- ab_sales_cash_accounting/views/cash_navigation.xml
