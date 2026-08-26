Commit: 3db5d59
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26
Subject: INIT commit pos19

User-facing changes:
- Existing contract sales logic provides E-Plus header extensions for contract invoices and total invoice discounts.

Files changed:
- ab_sales_contract

Current changes before commit:
- Update contract E-Plus header overrides to accept the new base `return_reuse` idempotency flag.
- Preserve contract-specific `sales_trans_h` updates while returning the reused-header metadata required by the retry-safe E-Plus push flow.

Files changed:
- ab_sales_contract/changelog.d/2026-08-26-eplus-header-reuse-compatibility.md
- ab_sales_contract/models/ab_sales_header_inherit.py
- ab_sales_contract/models/ab_sales_header_total_invoice_discount.py
