Commit: 0872f58fec68e9e8c9e486f1739f72a79cf98ff1
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26 16:05:24 +0300
Subject: ab_sales/fix: isolate POS header create failures with savepoint

User-facing changes:
- Keep failed POS invoice creation inside a savepoint so duplicate-token recovery can run safely.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/changelog.d/2026-08-26-eplus-detail-idempotency.md

Changes included in commit 04ead10b2aefe53d014ccdfb54b36f23b853fe86:

Author: hossam elsheikh
Date: 2026-09-08

- Add BRANCH_API_WORKFLOW.md with workspace setup, access/RPC configuration, sale/return flows, stock reads, connection checks, and reconciliation guidance.
- Route callcenter POS sale submission through the version 1 branch provider, preserving the existing immediate-push configuration flag. Send stable product, employee, customer, contract, promotion, and unit references instead of cross-database Odoo IDs.
- Exclude contract display values (company_pay, cust_pay, contract_name) from sale RPC headers; branch Odoo computes payment totals from the contract and sale lines. Preserve the contract reference and invoice discount input.
- Display branch XML-RPC business and access faults as handled Odoo messages, preserving the branch's translated text. Keep unexpected server faults technical for diagnosis.
- Route live stock batch reads and POS balance refreshes through the selected branch. Validate returned store/product identities and reject non-finite stock data. Split large refresh requests into batches of 200 products.
- Route return invoice loading, refund previews, and posting through branch Odoo. Preserve source-line identities, selected units, and employee session validation; branch posting always requests immediate E-Plus processing.
- Keep a durable return request token, capture branch/E-Plus result identifiers, and log return submissions. Preserve the request token after timeouts so retries can recover completed branch operations without reposting.
- Block direct E-Plus return connections and direct sale pushes for callcenter users. Other users retain the existing local flow.
- Test the provider capability/version and store binding from Branch RPC Configuration. Show the operation name in RPC logs and expose return correlation identifiers in the administrator return form.
- Declare the HR dependency used by employee reference mapping. Append Arabic translations to both existing PO files and add the missing ar_001 language header.

Validation:
- Mocked RPC fault checks passed in callcenter19 for authentication and execution: warning/access fault codes preserve Arabic messages as handled exceptions; unknown/server faults and successful responses remain unchanged. No network calls were made.
- Cash and contract payload regression checks passed in the callcenter19 Odoo registry: omit zero/nonzero display totals, preserve contract/discount inputs, match the provider header whitelist, and round-trip XML-RPC serialization. No sale was submitted.
- Targeted ab_sales upgrade passed on callcenter19. The initial upgrade exposed a pre-existing missing promotion field; a targeted ab_promo_program upgrade resolved that dependency schema mismatch without source changes to that module.
- Actual Odoo model tests with mocked branch RPC passed: stock mapping, cross-branch rejection, return loading and unit preservation, direct SQL denial, return posting response, stable sale references, and XML-RPC request/response serialization.
- The installed employee extension rejects return previews without employee login before any branch request; valid-session preview routing remains in the inheritance chain.
- Odoo 19 POT export, msgfmt --check-format for both PO files, and runtime en_US/ar_001 view/new-field-label checks passed.
- Validation used isolated processes with zero cron threads. No external E-Plus business writes were executed.

Deployment:
- Restart the callcenter Odoo process after upgrade.
- Configure Branch RPC Configurations for the desired branch Odoo URL/database/user and store, then use Test Connection.
- The remote branch must have the branch provider installed and an explicit access binding for the RPC user/store. Shared XML IDs are required for related records without a stable E-Plus serial/code, such as promotion programs.
- Product catalogue search continues to use the existing POS catalogue; live stock data and the sale/return transaction routes use the provider. The provider also exposes a product-search endpoint for integration consumers.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/security/ir.model.access.csv
- ab_sales/views/ab_sales_branch_api_views.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-09-07-branch-api-client.md
