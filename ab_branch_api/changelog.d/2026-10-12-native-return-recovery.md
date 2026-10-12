# Native call-center return posting and recovery

## Recent relevant commit

- Commit: `71c1fa4d9c1e3b9b11df6a70d1b12fc4eb49e9a3`
- Author: emadco88
- Date: 2026-10-08 01:33:29 +0300
- Original commit subject: ab_branch_api/ UPD compatible with callcenter19 ab_sales
- Adapted native sale posting to the API's retained connection factory while return posting still used the older journal/connection workflow.

Files changed (relevant excerpt):
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/reconciliation.py`
- `ab_branch_api/models/routing.py`

## Current changes before commit:

- Open a fresh native return connection using the factory retained in the authorized API scope; preserve branch query checks and disable reconnect/replay.
- Allow the native return workflow to own its commit and durable return-token marker instead of requiring legacy API deferred commits.
- Report native posting failures accurately and require Saved status plus both posting identifiers before marking an API operation successful.
- Recover native returns under the existing per-invoice locks using committed, branch-scoped marker reads. Restore confirmed results without reposting; permit retry only after confirmed absence. Preserve uncertainty for unavailable, incomplete, conflicting, or duplicate evidence.
- Use the internal return-state helper for authorized lifecycle recovery, retaining ordinary edit restrictions and the original API/native tokens.
- Extend the return query allowlist only for the native source-invoice lock and branch-filtered detail query, validating invoice/store parameters.
- Includes the earlier uncommitted fix removing undefined sale-default variables from existing return-header reuse, documented in the accompanying changelog.
- Reuse existing translated messages; no new user-facing strings, schema changes, hooks, or migrations.

Files changed:
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/reconciliation.py`
- `ab_branch_api/models/sales_workflow.py`
- `ab_branch_api/changelog.d/2026-10-12-return-header-reuse.md`
- `ab_branch_api/changelog.d/2026-10-12-native-return-recovery.md`

Validation:
- Executed native Odoo posting, API submit/replay, response validation, marker recovery, and state helpers with fake SQL Server connections and business posting mocked. PostgreSQL commits were suppressed during tests, and all test changes were rolled back.
- Passed fresh factory/no-reconnect behavior; supported source/detail queries; wrong-branch/unscoped query rejection; existing Unknown recovery; committed, absent, incomplete, duplicate, unavailable, and conflicting marker cases; ordinary edit protection; concurrent invoice-lock rejection; native success; acknowledged rollback; lost commit response; same-token replay; accurate failure propagation; and changed-payload rejection.
- Script: `/tmp/test_branch_native_return.py`; diagnostic log: `/tmp/branch-native-return-validation.log`.
- Python parsing, `git diff --check`, and both Arabic catalogs' `msgfmt --check-format` passed. Existing English/Arabic messages were reused without changing their wording.

Development deployment and recovery:
- Gracefully reloaded only the local branch Odoo master serving port 4092; confirmed new workers, completed registry loading, and HTTP 200 from the login endpoint.
- Called authenticated `reconcile_operation` for existing API operation 2 / return 2753 / source invoice 24743 on `abdin_old_pos19`. HTTP 200 returned `retryable` after locked external-marker absence was confirmed.
- Verified persisted return status `prepending`, zero return/finance identifiers, and operation state `retryable`. Original tokens retained. Reconciliation performed external reads/locks only; no refund or other E-Plus business write was submitted.
- No module upgrade was needed for this Python-only correction. The existing return is ready for the user's normal Retry action.
