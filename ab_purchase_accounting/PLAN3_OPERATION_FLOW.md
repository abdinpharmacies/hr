# Plan 3 Purchase Accounting Operation Flow

The live-state notes below are historical observations from before the first-copy
accounting restoration. They are not verification of the current live database.
The adapter now uses the original journal fields and validates mappings at posting.
Inventory accounts must be under the inventory XML-ID account, tax accounts under
the taxes XML-ID account, and supplier accounts must be payable liabilities or
liabilities under the supplier XML-ID account. All must be active final accounts.
The posting user must own the supplier and receipt-offset header accounts and be
authorized for every line account and both document types.

Source supplier workbook: `/home/abdin_04/Documents/Share/abdin_dev__plan/Suppliers_data.xlsx`

## Current Live State

- `ab_purchase_accounting` is installed on `rip_bconnect`.
- `ab_purchase_ob` is installed and Odoo 19 compatible enough for module loading.
- `ab_purchase_accounting_config` has `1` manual-test record for branch code `94` (`فرع برج القضاة سوهاج`).
- The live database currently has:
  - `158` `ab_supplier` records imported from the workbook for manual testing.
  - `4` `ab_accounting_account_guide` records for Plan 3 manual testing.
  - `2` `ab_accounting_doctype` records.
  - `1` open `ab_accounting_period` record for 2026.
  - `1` `ab_purchase_ob_receipt_type` record and `1` receipt-offset mapping.
  - Active purchase stores and product/UoM data are available.

## Workbook Summary

The workbook has one sheet, `vendor`, with 158 supplier rows.

Columns:

- `I.D`: supplier code.
- `SUPPLIER`: supplier name.
- `TAX`: supplier accounting/tax category.
- `SECTION`: product/supplier section.
- `المنطقة`: supplier territory.

Category counts:

- `TAX`
  - `ضريبي`: 93 suppliers.
  - `دفعات مقدمة`: 40 suppliers.
  - `غير ضريبي`: 25 suppliers.
- `SECTION`
  - `تجميــــــــــــــــــــــل`: 67.
  - `ادويـــــــــــــــــــــــــــة`: 61.
  - `مــــــســـتـــــــــلــــــزمـــــــات`: 17.
  - `مـــــســــتـــــورد_أدويـــــــــــــة`: 9.
  - `مـــــســــتـــــورد_تــــجــــمـــيـــل`: 3.
  - `مستحضرات طبية`: 1.
- `المنطقة`
  - `القاهرة`: 98.
  - `الصعيد`: 60.

Representative suppliers for tests:

| Test role | Code | Supplier | TAX | Section | Territory |
| --- | --- | --- | --- | --- | --- |
| Advance/prepayment supplier | `1470` | `ابن سينا` | `دفعات مقدمة` | `ادويـــــــــــــــــــــــــــة` | `الصعيد` |
| Taxed supplier | `103` | `مخزن الصيادلة فارم` | `ضريبي` | `ادويـــــــــــــــــــــــــــة` | `الصعيد` |
| Non-tax supplier | `1536` | `مخزن انجيلنا فارما` | `غير ضريبي` | `ادويـــــــــــــــــــــــــــة` | `الصعيد` |

## Supplier Mapping

Use the workbook rows to create `ab_supplier` records.

Suggested field mapping:

| Workbook column | Odoo field | Mapping rule |
| --- | --- | --- |
| `I.D` | `code` | Use as-is; keep unique. |
| `SUPPLIER` | `name` | Trim whitespace. |
| `TAX = ضريبي` | `tax_type` | `through_supplier` |
| `TAX = غير ضريبي` | `tax_type` | `non_tax_payment` |
| `TAX = دفعات مقدمة` | `tax_type` | `tax_payment` as the current closest system value; split later if advance-payment accounting gets its own account flow. |
| `SECTION = ادوي...` | `section` | `medical` |
| `SECTION = مستورد_أدوية` | `section` | `imp_med` |
| `SECTION = تجميل` | `section` | `cosmo` |
| `SECTION = مستورد_تجميل` | `section` | `imp_cosmo` |
| Other section text | `section` | `other` |
| `المنطقة = الصعيد` | `territory` | `upper_egypt` |
| `المنطقة = القاهرة` | `territory` | `lower_egypt` placeholder mapping until a Cairo-specific value exists. |

Cost centers:

- Preferred: create one `ab_costcenter` per supplier and set `supplier.costcenter_id`.
- Test shortcut: create one shared supplier cost center, for example `SUP-TEST`, and reuse it for all test suppliers if the selected accounting accounts require cost centers.

## Manual Accounting Setup

The live DB already has this minimum setup for manual Plan 3 testing. Reuse it for the first manual cycle, or replace it with production accounts/document types before business use.

Company:

- Use the active Odoo company in the test user context.

Branch:

- Use store code `94` (`فرع برج القضاة سوهاج`) for the seeded manual-test cycle.

Posting user:

- Use a dedicated user with `ab_accounting.group_ab_accounting_accountant`.
- Temporary test shortcut: the seeded manual-test setup uses admin/system as the posting user.

Document types:

- `PUR-REC`: purchase receipt doctype, `internal_type = payable`.
- `PUR-RET`: purchase return doctype, `internal_type = payable`.

Accounts:

| Code | Name | Group | Type | Notes |
| --- | --- | --- | --- | --- |
| `P3-1200` | PLAN3 Manual Inventory | `asset` | `other` | Posting account, no partner required. |
| `P3-1210` | PLAN3 Manual Purchase VAT | `asset` | `other` | Posting account, only needed for taxed purchases/returns. |
| `P3-2100` | PLAN3 Manual Suppliers Payable | `liability` | `payable` | Posting account, no partner required until suppliers are linked to `res.partner`. |
| `P3-2200` | PLAN3 Manual Non-purchase Receipt Offset | `liability` | `other` | Used as the credit offset for non-purchase receipt types. |

Important constraints:

- The accounting baseline uses no partner field; supplier dimensions use the existing cost center.
- If any configured account has `has_costcenter = True`, each tested supplier must have `costcenter_id`, or set `default_costcenter_id` on `ab_purchase_accounting_config`.
- Create exactly one open `ab_accounting_period` for the company, branch, and document date used in tests.

Adapter configuration:

Create one `ab_purchase_accounting_config`:

- `company_id`: active company.
- `branch_id`: chosen store.
- `activation_date`: start date of the test period.
- `posting_user_id`: Auto JE user.
- `purchase_doctype_id`: `PLAN3 Manual Purchase Receipt`.
- `return_doctype_id`: `PLAN3 Manual Purchase Return`.
- `inventory_account_id`: `P3-1200`.
- `tax_account_id`: `P3-1210`.
- `supplier_account_id`: `P3-2100`.
- `default_costcenter_id`: shared cost center if required.
- `receipt_account_ids`: seeded receipt type `P3-NPR` maps to offset account `P3-2200`.

## Receipt Operation Flow

1. Create/import supplier from workbook.
2. Confirm test product and UoM exist.
3. Create draft purchase invoice in `ab_purchase_header`:
   - Branch/store = configured branch.
   - Supplier = workbook supplier.
   - Document date inside the open accounting period and on/after adapter activation date.
   - `net_invoice` and `net_tax` must match line totals.
4. Add purchase line with existing product source data.
5. Submit purchase invoice to pending inventory.
6. Save and receive purchase invoice.
7. Expected result:
   - Purchase status becomes `saved`.
   - Inventory movement is posted.
   - One posted journal is created and linked on `purchase_accounting_journal_id`.
   - Journal source is `ab_purchase_header`.

Expected journal for taxed receipt:

| Line | Debit | Credit |
| --- | ---: | ---: |
| Inventory | net invoice minus tax | 0 |
| Purchase VAT | tax | 0 |
| Supplier payable | 0 | net invoice |

Expected journal for non-tax receipt:

| Line | Debit | Credit |
| --- | ---: | ---: |
| Inventory | net invoice | 0 |
| Supplier payable | 0 | net invoice |

## Return Operation Flow

1. Use a saved purchase invoice that already has a receipt journal.
2. Create purchase return through the existing purchase return action.
3. Select one or more purchase lines and return quantities within allowed limits.
4. Submit the return.
5. Expected result:
   - Return status becomes `saved`.
   - Inventory return movement is posted.
   - One posted journal is created and linked on the return `purchase_accounting_journal_id`.
   - Journal source is `ab_purchase_notice_header`.

Expected journal for taxed return:

| Line | Debit | Credit |
| --- | ---: | ---: |
| Supplier payable | returned total including tax | 0 |
| Purchase VAT | 0 | returned tax |
| Inventory | 0 | returned total minus tax |

## Non-purchase Receipt Flow

1. Create a receipt type from `Receipt Types`, for example `FREE-STOCK` or `SUPPLIER-GIFT`.
2. Add a matching row on `Purchase Accounting` configuration:
   - Receipt Type = the new receipt type.
   - Offset Account = configured non-purchase receipt offset account.
3. Open `Non-purchase Receipts`.
4. Create a receipt:
   - Purpose defaults to `Non-purchase Receipt`.
   - Branch/store = configured branch.
   - Receipt type = mapped receipt type.
   - Document date inside the open accounting period and on/after adapter activation date.
5. Add receipt lines with product, quantity, price, purchase price, taxes, and unit cost.
6. Submit the receipt.
7. Expected result:
   - Receipt status becomes `saved`.
   - Inventory movement is posted.
   - One posted journal is created and linked on `purchase_accounting_journal_id`.
   - Journal source is `ab_purchase_ob_header`.

Expected journal:

| Line | Debit | Credit |
| --- | ---: | ---: |
| Inventory | receipt total cost | 0 |
| Configured receipt offset | 0 | receipt total cost |

## Required Negative Tests

Run these before declaring Plan 3 receipt/return slice complete:

1. Missing `ab_purchase_accounting_config`
   - Action: save a pending purchase receipt for a configured branch/date with no config.
   - Expected: validation error; purchase status and inventory posting roll back.

2. Missing tax account on taxed purchase
   - Action: configure inventory/supplier accounts only and post a taxed purchase.
   - Expected: validation error; purchase status and inventory posting roll back.

3. Missing open accounting period
   - Action: post receipt outside open period.
   - Expected: accounting validation error; purchase status and inventory posting roll back.

4. Repeated save action
   - Action: run save again on an already saved purchase.
   - Expected: no duplicate journal.

5. Return over original quantity
   - Action: return more than unreturned quantity.
   - Expected: purchase return validation error; no inventory or journal side effect.

6. Opening balance
   - Action: submit `ab_purchase_ob_header`.
   - Expected: inventory only; no accounting journal generated by `ab_purchase_accounting`.

7. Existing saved documents
   - Action: inspect saved documents created before adapter installation.
   - Expected: no automatic backfill journal.

8. Missing non-purchase receipt offset
   - Action: submit a non-purchase receipt whose receipt type has no offset account mapping.
   - Expected: validation error; receipt status and inventory posting roll back.

## Completion Gates

Plan 3 receipt/return slice is complete when:

- Supplier test data exists from the workbook mapping.
- Manual or real accounting accounts, doctypes, open period, and adapter config exist.
- A taxed purchase receipt creates exactly one balanced posted journal.
- A non-tax purchase receipt creates exactly one balanced posted journal without a tax line.
- A purchase return creates exactly one balanced reversal-effect journal.
- A non-purchase receipt creates exactly one balanced posted journal against its configured offset account.
- The missing-config and missing-period tests roll back both stock and document status.
- Opening balances remain inventory-only.

## Remaining Plan 3 Work After This Slice

These are not complete yet and should be implemented only after their base contracts are ready:

- Supplier claim accounting.
- Later cost-correction accounting.
- Dedicated advance-payment/prepayment supplier flow if `دفعات مقدمة` must post to a separate advance account instead of the generic supplier payable account.
- Partner-linked supplier payable accounts, if accounting decides payable accounts must require `res.partner`.
