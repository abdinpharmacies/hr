Current changes before commit:

- Add shared branch cash drawers with fixed Cairo periods, responsible cashiers and explicit opening acceptance.
- Record split cash/card/wallet/other payments and refunds in an immutable shift ledger; keep stock posting at cashier settlement.
- Close with an explained discrepancy awaiting Finance review, split counted cash into treasury transfer and next float, and require receipt acknowledgements.
- Recover delayed unaccepted handovers through an audited manager action without changing the float.
- Include explicit Odoo 19 form-view descriptors in handover, setup, receipt and review actions so dialogs open from the JavaScript client.
- Add a module-scoped Shift Cashier interface, branch/company security and both Arabic catalogs.
- Group setup, operations and reports under Sales → Cash Management, add treasury form entry and a Finance review list, and explain activation prerequisites.
- Keep branch activation explicit and remote reporting disabled; do not alter core sales, inventory, purchase or tax code.

Validation: Targeted installation and upgrades on rip_bconnect; 95 workflow/security checks passed previously; the Cash Management section passes 29 bilingual view/asset checks plus menu and Finance-filter assertions; evidence is recorded in scripts/stock_integration_validation/VALIDATION.md. Initial cash tests rolled back; the explicitly authorized full live cycle is now retained for branches 29 and 140, with next openings awaiting receipt and validation sessions closed. The new Accounting bridge is installed and the handover action repair passed the complete six-check Playwright flow.

Files changed:

- ab_sales_cash_shift/README.md
- ab_sales_cash_shift/__init__.py
- ab_sales_cash_shift/__manifest__.py
- ab_sales_cash_shift/changelog.d
- ab_sales_cash_shift/i18n/ar.po
- ab_sales_cash_shift/i18n/ar_001.po
- ab_sales_cash_shift/models/__init__.py
- ab_sales_cash_shift/models/cash_shift.py
- ab_sales_cash_shift/models/integration.py
- ab_sales_cash_shift/security/ir.model.access.csv
- ab_sales_cash_shift/security/record_rules.xml
- ab_sales_cash_shift/security/security_groups.xml
- ab_sales_cash_shift/static/src/cashier.js
- ab_sales_cash_shift/static/src/cashier.xml
- ab_sales_cash_shift/views/cash_shift.xml
- ab_sales_cash_shift/wizard/__init__.py
- ab_sales_cash_shift/wizard/operations.py
- ab_sales_cash_shift/wizard/operations.xml
