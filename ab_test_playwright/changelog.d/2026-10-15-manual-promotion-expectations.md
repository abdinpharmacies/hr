## 939c058e0d4ed8abe4769fa0d474b44b0f9c84ce - emadco88 - 2026-10-14 21:13:35 +0300

Original commit subject: ab_test_playwright/sales_ui_cases.json FIX JSON file

- Restore valid JSON syntax for the sales UI scenarios.

Files changed:

- ab_test_playwright/sales_ui_cases.json

Current changes before commit:

- Preserve the user's removal of automatic promotion-selection test steps from the original scenarios.
- Expect customer payment of 281, no applied promotion, and zero promotion discount in the three original contract/manual-selection scenarios.
- Rename CONTRACT_CLEAR_RESTORES_PROMO to CONTRACT_CLEAR_NO_AUTO_PROMO to describe its actual expectation.
- Add four preview cases covering explicit promotion selection after a contract, contract changes 4 to 1 to 4, explicit selection after contract removal, and quantity updates retaining the selection.
- Add strict unselected/applied chip assertions, an explicit click action that rejects preselected promotions, and intermediate UI-total expectations.
- Wait for browser RPC completion and a quiet interval covering pricing debounces before checking pricing; validate integrated contract quotes with store, customer, and selection inputs.
- Update the action registry and README for the fifteen-case suite. Existing fixtures and preview-only execution remain unchanged.

Files changed:

- ab_test_playwright/actions.json
- ab_test_playwright/sales_ui_cases.json
- ab_test_playwright/sales_ui_runner.mjs
- ab_test_playwright/README.md
- ab_test_playwright/changelog.d/2026-10-15-manual-promotion-expectations.md

Verification:

- Validated fifteen unique cases, registered actions, preview-only steps, JSON syntax, JavaScript syntax, and whitespace.
- Passed isolated Chromium checks exercising the runner's manual-click/state/totals assertions, contract RPC inputs, incorrect selection rejection, and delayed/debounced RPC settling.
- Passed the existing simulated submission and saved-invoice validation checks, including action-registry consistency.
- The supplied eleven-case preview report recorded customer payment of 281 for the three original failures. The expanded live Odoo suite was not rerun because runtime password/PIN credentials were unavailable.
- Isolated browser verification remains outside the addon at /opt/playwright/tasks/replica_addons/manual_promo_assertions/check.mjs. No application UI strings or translation catalogs changed.
