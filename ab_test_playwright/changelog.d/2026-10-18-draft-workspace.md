## 26bd1ed8e2d623bc7249c1975f2043e9756aa1e4 - emadco88 - 2026-10-17 11:02:10 +0300

Original commit subject: ab_test_playwright/ add new tests

- Expand sales scenarios and manual-promotion expectations and assertions.

Files changed:

- ab_test_playwright/README.md
- ab_test_playwright/actions.json
- ab_test_playwright/changelog.d/2026-10-15-manual-promotion-expectations.md
- ab_test_playwright/sales_ui_cases.json
- ab_test_playwright/sales_ui_runner.mjs

Current changes before commit:

- Fix the new_empty_bill timeout caused by waiting for a server save of a local-only Ready bill.
- Read selection from the tab's scoped workspace instead of cache-save responses, which no longer receive the selected ID.
- Claim only newly created case bills and obtain their submission tokens from the workspace.
- Remove a case bill with one UI click and verify workspace removal for both local and saved drafts; preserve other bills.
- Document the updated draft lifecycle in the runner.

Files changed:

- ab_test_playwright/sales_ui_runner.mjs
- ab_test_playwright/draft_workspace.mjs
- ab_test_playwright/README.md
- ab_test_playwright/changelog.d/2026-10-18-draft-workspace.md

Verification:

- Isolated Chromium checks passed for local Ready ownership without RPC, scope isolation, missing-workspace rejection, and immediate/delayed cleanup with one click while preserving an existing bill.
- Existing submission simulations and saved-invoice validation passed; JavaScript syntax and diff whitespace checks passed.
- Browser fixture: /opt/playwright/tasks/replica_addons/draft_cache_check/check.mjs.
- Live Odoo suite not rerun: runtime password and employee PIN were unavailable.
- No application UI text or translation catalogs changed.
