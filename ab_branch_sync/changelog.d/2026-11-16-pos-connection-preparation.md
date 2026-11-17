Current changes before commit:

- Prepare the saved central connection and first stock snapshot when the POS selects a branch, including before employee PIN login.
- Separate branch-user/store authorization from stock readiness. Preparation may initialize an unready branch; normal sale, return and stock operations still require successful enrollment and a complete snapshot.
- Keep preparation limited to local replica stores and the existing POS service-user binding. Credentials remain server-side. Setup does not replay sales or grant central permissions.
- Save authorization and the full initial snapshot in one savepoint; failure rolls back partial setup. Already-ready selections reuse readiness, while authenticated periodic synchronization retains its employee checks and delivery behavior.
- Use a module-owned POS action subclass to await preparation before opening/changing bills or loading stock for restored drafts. Deduplicate concurrent preparation requests and discard stale branch/bill results.
- Allow the status tag to prepare/retry before PIN login, display setup failures and follow the login panel's selected store.
- Retain existing English/Arabic messages and update the exported POT reference in both Arabic catalogs. Update setup documentation and bump the branch module to 19.0.5.1.2.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/static/src/pos/central_status.js
- ab_branch_sync/static/src/pos/central_status.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-16-pos-connection-preparation.md

Verification:

- `/tmp/test_branch_pos_prepare.py`: transactional backend checks passed for initial preparation without employee login, repeat selection, failed-page rollback, network/403/503 failures, central store/protocol/replica mismatch, missing credentials, foreign/public/service-user denial, and preserved employee checks for periodic delivery. Network and snapshot delivery were mocked; all test writes rolled back.
- `/tmp/test_branch_pos_prepare.mjs`: control-flow checks passed for waiting before bill/stock loading, failed initialization, shared in-flight requests, stale bill/branch responses, pre-login status, restored drafts and authenticated periodic synchronization. The shared base action prototype is not modified by the new subclass.
- Odoo JavaScript transpilation, Node syntax, Python/XML parsing, both `msgfmt --check-format` checks and `git diff --check` passed.
- Targeted `ab_branch_sync` upgrade exited 0 and the branch service was gracefully reloaded. Existing duplicate-cache/missing-module warnings are unchanged from the preceding repair.
- Live installed RPC dispatch returned online/ready for authorized store 29; its existing snapshot was reused. Version 19.0.5.1.2 and Arabic action translation were verified; port 4097 returned HTTP 200.
- Tests exercised backend and frontend control flow; no connected browser was available for visual POS verification. No test sale or central inventory posting was performed.

Recent relevant commit:

- Commit: d640ec240c3fbee8dd8afa2905ba1454b5b6fbb5
- Author: hager yasser
- Date: 2026-11-11
- Original subject: ab_branch_sync/FEAT: rename central connection parameters to ab_central_branch_connection
- Use the current namespace for the saved central connection and synchronization state.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/changelog.d/2026-11-11-connection-parameter-namespace.md
- ab_branch_sync/data/config.xml
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/workflow.md
