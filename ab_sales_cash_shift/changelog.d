Current changes before commit:

- Keep the original Cashier client action as the single operational screen and retain the old Shift Cashier action XML ID as an inactive compatibility alias.
- Replace scheduled, acceptance-gated shifts with one employee-owned active wallet per branch, created with a zero opening balance by the first authorized collection when needed.
- Close wallets by splitting counted cash between treasury delivery and the next cashier opening, while recording non-blocking shortages or surpluses and independent receipt confirmations.
- Enforce active-wallet uniqueness at the database level, preserve immutable history, and migrate active legacy waiting shifts without replaying accounting.
- Add an attachment-backed QWeb PDF closing report and bilingual wallet terminology.
- Extend the original Cashier component through a module-scoped patch and preserve the legacy cashier fallback for stores without a configured drawer.
- Fix the cashier patch object syntax so the backend JavaScript bundle loads after Odoo sign-in.
- Restore the original Cashier direct-save behavior, automatically recording the full sale as cash and deriving refunds from their original payment methods without requiring a manual total-equality check.
- Restore the original Close Cashier dialog with its cashier employee, opening balance and editable net balance fields for configured native branches.
- Close the active employee wallet from that legacy dialog without creating treasury transfers or accounting entries, leaving all post-close cash management work outside the cashier transaction.
- Preselect and validate the employee from the active branch PIN session while preserving zero-balance automatic opening for the next collection.

Validation: Targeted upgrades passed. The latest rollback lifecycle passed 55 assertions across branches 29 and 140, including direct Cashier save without a payment breakdown, five PIN profiles, blocked E-Plus connectors, stock/payment/wallet/accounting fingerprint restoration, active-wallet ownership and uniqueness, both handover paths, discrepancy handling, report rendering and balanced accounting. Authenticated debug and minified Cashier screens rendered without browser errors; the bilingual view/asset harness passed 33 checks for Owl templates, action/menu compatibility, report registration and Arabic runtime output. A targeted rollback test on branch 29 wallet 50 loaded the old dialog at 7,520, closed it with zero accounting entries and transfers, created the next zero opening on demand, and restored every record after rollback. The live Cashier screen again renders the Close Cashier button and legacy form structure.

Files changed:

- ab_sales_cash_shift/README.md
- ab_sales_cash_shift/__manifest__.py
- ab_sales_cash_shift/changelog.d
- ab_sales_cash_shift/i18n/ar.po
- ab_sales_cash_shift/i18n/ar_001.po
- ab_sales_cash_shift/migrations/19.0.1.1.0/post-migrate.py
- ab_sales_cash_shift/models/cash_shift.py
- ab_sales_cash_shift/models/integration.py
- ab_sales_cash_shift/reports/cash_wallet_report.xml
- ab_sales_cash_shift/static/src/cashier.js
- ab_sales_cash_shift/static/src/cashier.xml
- ab_sales_cash_shift/views/cash_shift.xml
- ab_sales_cash_shift/wizard/operations.py
- ab_sales_cash_shift/wizard/operations.xml

Earlier uncommitted changes:

- Depend on the optional native cashier and employee cashier bridge so shift operations load only with the cashier stack.
- Repair the Shift Cashier client-action registration by importing the employee cashier patch from its module-owned Odoo alias.
- Validate enabled drawer access through the native sales backend so Sales Managers are not rejected by lower inventory-user branch rules.
- Apply the manager-first branch guard consistently to drawer, treasury, shift, event, tender and transfer records.
- Authorize drawer stock locks through the native cashier guard before the scoped elevated lock.

Validation: Debug and minified Shift Cashier assets passed Playwright checks. Five employee profiles passed both allowed branches and one denied-store request each. The branch 29 sale, settlement, close and treasury-receipt lifecycle passed with its full business fingerprint restored by rollback. The final minified port-4097 smoke rendered without employee login or financial operations.

Files changed:

- ab_sales_cash_shift/__manifest__.py
- ab_sales_cash_shift/changelog.d
- ab_sales_cash_shift/models/cash_shift.py
- ab_sales_cash_shift/security/record_rules.xml
- ab_sales_cash_shift/static/src/cashier.js

Previous current changes:

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
