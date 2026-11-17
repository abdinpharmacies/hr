# Purchase submission safety, forms, and administrator access

## Current changes before commit:
- Allow Store selection on new/prepending purchase invoices through the form view.
- Keep Store read-only for pending, saved, and rejected invoices.
- Preserve the purchase-enabled store domain, computed fields, and existing workflow rules.
- Remove the browser-only required flag from the read-only journal header link so automatic journal creation can run when a new purchase is saved.
- Preserve the backend required relationship and genuine header/line requirements.
- Allow administrators to create purchases while preserving non-admin Branch user restrictions and existing read, write, and delete rules.

- Validate invoice quantities, units, totals, and taxes before stock or journal posting; preserve the existing 0.5 amount tolerance.
- Reject empty invoices and zero/negative notice or purchase quantities (positive bonus-only lines remain valid).
- Reject excess credit returns, including duplicate source lines, cumulative returns, bonus overreturns, and concurrent submissions; validate the source store.
- Post debit notices with Inventory/VAT debits and Supplier credits; preserve credit notice direction.
- Make submission atomic and reject repeat submissions without replacing existing journal lines.
- Remove the notice form's browser-only required journal link while preserving the backend required relationship.
- Add Arabic validation messages for both ar and ar_001 and translate the notice lines tab.
- Verify 19 backend cases, competing returns and duplicate submissions, Playwright purchase/notice flows, and runtime Arabic translations on an isolated database with external network access blocked. Existing live business documents are not repaired or submitted by this change.

Files changed:
- models/ab_purchase_header.py
- models/ab_purchase_je_header_delegate_common.py
- models/ab_purchase_notice_header.py
- models_accounting/ab_purchase__header_inherit.py
- models_accounting/ab_purchase__notice_inherit.py
- views/ab_purchase_notice_header.xml
- i18n/ar.po
- i18n/ar_001.po
- security/record_rules_purchase_header.xml
- views/ab_purchase_header.xml
- changelog.d/2026-11-15-purchase-store-view.md

## eda7652b65af99f01c606231fd5a44969a6f943a
Author: hossam elsheikh
Date: 2026-11-12
Subject: ab_purchase/FIX: repair purchase forms and show invoice details

- Repair purchase form layout and contain embedded table scrolling.
- Show purchase details on new invoices.

Files changed:
- views/ab_purchase_header.xml
- views/ab_purchase_notice_header.xml
- views_accounting/ab_purchase_claim.xml
