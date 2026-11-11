# Callcenter stock validation and customer/contract references

## Recent commit reviewed

- Commit: `71c1fa4d9c1e3b9b11df6a70d1b12fc4eb49e9a3`
- Author: emadco88
- Date: 2026-10-08 01:33:29 +0300
- Original commit subject: ab_branch_api/ UPD compatible with callcenter19 ab_sales
- Added protected token/revision submission and retry recovery.

Files changed (relevant excerpt):
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/guarded_sales.py`
- `ab_branch_api/models/callcenter_services.py`

## Current changes before commit:

- For authorized branch API requests, validate shortages against fresh branch product balances rather than the Odoo line's offline inventory snapshot. Ordinary POS validation retains its existing implementation.
- Reuse the existing branch-filtered, parameterized committed-read balance query; do not add NOLOCK. The source and normalization match callcenter's live balance API. No external inventory writes or direct computed stock-field edits are introduced.
- Aggregate repeated product quantities after unit conversion. Retain the existing 0.025 tolerance and shortage reason/Other-details requirements.
- Return requested quantity, available balance and base unit for missing reasons. Distinguish missing/inactive stock data and stock-read failures from confirmed zero stock. Read fresh balances on rejected retries; accepted and uncertain recovery paths retain existing idempotency behavior.
- Reject invalid, nonfinite, nonpositive or disallowed sale-unit factors instead of silently changing the selected unit.
- Check contract branch restrictions before preparing a branch header. Return explicit synchronization guidance for missing, inactive or ambiguous customer/contract references.
- Resolve customer lookup against the selected branch E-Plus result, rather than returning the first stale local phone match. Update only the exact accessible active customer resolved by its stable external identifier.
- Import verified E-Plus customers into branch Odoo on lookup, registration and missing invoice-reference resolution, without requiring prior customer replication. Preserve their E-Plus IDs.
- Grant customer creation to the existing Call Center and Sales Manager groups through module-owned ACLs, without granting customer write/delete access.
- Serialize API registrations per branch and local customer imports per E-Plus reference; retain operation-token replay protection and reject archived, duplicated or inaccessible identities.
- Export the module POT and append new Arabic translations to both catalogs. Version: `19.0.5.5.3`.

Files changed:
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/callcenter_services.py`
- `ab_branch_api/models/sale_validation.py`
- `ab_branch_api/models/customer_sync.py`
- `ab_branch_api/models/guarded_sales.py`
- `ab_branch_api/security/ir.model.access.csv`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/changelog.d/2026-10-12-callcenter-validation.md`

## Validation

- Isolated POS database: `codex_ccfix_pos19_20261012`; targeted `-u ab_branch_api`, alternate ports 5079/5082, `--stop-after-init --workers=0 --max-cron-threads=0`.
- 23 ORM checks passed: stale-zero cache/live stock, duplicate-line totals and reasons, alternate units, tolerance, valid reasons, blank/filled Other details, missing/nonfinite/wrong-branch stock, read timeout, fresh rejected retry, public-user denial, ordinary POS fallback, missing/inactive references, contract branch restriction, missing phone, stale local customer avoidance and runtime Arabic stock message.
- 15 callcenter ORM and 12 frontend checks passed separately. Development harnesses: `/tmp/test_callcenter_regressions.py` and `/tmp/test_callcenter_frontend.cjs`; detailed logs remain under `/tmp`. No test fixtures or harnesses are shipped inside the addon.
- Python syntax, imports and `git diff --check` passed. Both Arabic catalogs passed `msgfmt --check-format`; runtime Arabic shortage text was verified.
- Targeted upgrade completed. Existing data warning: 85 original POS return headers have no `store_id`, preventing the existing required-field NOT NULL constraint from being applied. This predates the changes and was not repaired by guessing historical branches.
- Local API credentials/routing work. Live product-balance request returned HTTP 422 because the configured store E-Plus endpoint is unreachable. External posting, new customer creation and final posted contract totals were not exercised.
- Neither user-managed server was restarted, and active databases were not upgraded. Activate through the normal restart/targeted-upgrade process. The remote branch responsible for the original reported invoice also needs this release.

## Manual acceptance

Verify sufficient/insufficient stock, repeated products, fractional/alternate units, tolerance, Other details, unavailable stock reads, replenishment followed by same-token retry, inactive/missing products, valid/restricted/missing contracts, branch-confirmed customers, archived/ambiguous customer mappings and duplicate/timeout recovery. Compare contract customer/company amounts and printed totals for zero, fixed and percentage contributions using approved test transactions. Confirm direct RPC cannot cross branch/user scope. Verify English and Arabic messages.

## Customer registration follow-up — 2026-10-13

- Confirmed cause: the existing POS `_upsert_customer_from_bconnect` refused missing Odoo customers with a replication-required error. Branch lookup also required an existing Odoo reference before returning an E-Plus customer. Newly registered or not-yet-replicated customers therefore could not be selected reliably for a callcenter invoice.
- API-only override creates the authorized local customer from branch E-Plus data. Ordinary POS behavior outside an authenticated API scope is unchanged. No customer is selected by an ambiguous local phone match, and no archive is silently reversed.
- Existing customers retain their home branch. Missing E-Plus identities receive instructions to search by phone and register through the customer dialog; the API does not fabricate external IDs or silently merge customers.
- Lookup commits its imported reference before releasing the identity lock. Sale preparation acquires the reference lock before its savepoint. New-customer API requests keep their existing durable operation record and external business workflow.
- Read-only diagnosis found customer ID sequences behind existing records on both active local databases: maximum customer ID 497944, sequence 497942. A bounded maintenance operation advanced each sequence to 497944 under a short table lock. No customer records were changed. No migration/hook was added.
- 20 focused tests passed on the isolated POS database, covering creation without replication, lookup/import, sale-reference resolution, repeated requests, changed token payloads, external identity mismatch, archived/duplicated/inactive records, permissions, scope enforcement and ordinary POS fallback. External customer operations were mocked and Odoo test records rolled back. Harness: `/tmp/test_branch_customers.py`.
- Final validation: all 20 customer tests and 23 existing branch regression tests passed (43 total). Targeted isolated upgrade, Python syntax, diff whitespace and both Arabic catalog format checks passed. Runtime checks found all six relevant customer messages translated in both Arabic catalogs, and the Arabic Branch API Operations action differs from English. Logs: `/tmp/branch_customer_test_results.log` and `/tmp/branch_customer_existing_regressions.log`. Live E-Plus creation/posting remains a manual acceptance check.
- Active processes were not restarted and active modules were not upgraded. Activate `ab_branch_api` version `19.0.5.5.3` on each destination branch, including the remote branch used by the invoice. Only the bounded sequence repair was applied to the active databases.

Manual customer acceptance:
1. From callcenter, select the target branch and search for a phone absent in that branch. Enter the customer's valid name/address, create, select, and submit an approved test invoice. Confirm it references the returned customer E-Plus ID.
2. Search for an E-Plus customer absent from branch Odoo. Confirm it is imported once and immediately selectable without waiting for replication.
3. Repeat the same creation request and reload the customer dialog. Confirm one customer identity is reused.
4. Retry the rejected invoice after its missing branch Odoo reference is imported. Keep the original invoice token.
5. Verify duplicate or archived customer mappings are rejected without merging/reactivating records; verify an unauthorized user cannot create a customer.
6. Test two simultaneous API registrations for the same branch. The second should retry after the first finishes, then reuse an existing phone match when appropriate.
7. Simulate loss of the response after external customer creation. Search the phone to confirm the existing branch customer; do not replay an uncertain operation blindly.
8. Check the Arabic message and the branch-specific result. An unavailable E-Plus endpoint or no available spare customer must produce a business error rather than a fabricated customer.
