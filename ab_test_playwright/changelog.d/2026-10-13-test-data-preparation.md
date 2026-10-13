# Test data preparation

No previous commits exist for this standalone tooling folder.

## Current changes before commit:

- Add a read-only preview and transactional SQL preparation command for the agreed development records.
- Mark 13 names as test data while preserving record identifiers and business settings.
- Reset the selected Odoo login using a compatible password hash supplied at runtime.
- Back up original field values with restricted permissions and exclude backups from Git.
- Add a local Playwright login verification command without persisted credentials.
- Document setup, repeatability, and the boundary between data preparation and future sales recording.
- Add eleven JSON sales cases for the selected products, customer, branch, employee, contracts and promotion.
- Configure contracts 1–3 from the old JSON percentages and origin discounts; configure contract 4 for eligible promotion use and reactivate the fixed-price test promotion.
- Add an interactive/headless Playwright preview runner with real Odoo pricing checks, shortage reasons, screenshots and run-owned draft cleanup.
- Record nine passing preview cases and two combined contract/promotion UI regression failures; final posting remains unexecuted.

Files changed:

- `ab_test_playwright/.gitignore`
- `ab_test_playwright/prepare_test_data.py`
- `ab_test_playwright/verify_login.mjs`
- `ab_test_playwright/README.md`
- `ab_test_playwright/changelog.d/2026-10-13-test-data-preparation.md`
- `ab_test_playwright/prepare_sales_scenarios.py`
- `ab_test_playwright/run_sales_ui.py`
- `ab_test_playwright/sales_ui_runner.mjs`
- `ab_test_playwright/sales_ui_cases.json`
- `ab_test_playwright/validation_results.json`

Validation: Python syntax and read-only preview passed; SQL updates committed and
were independently read back; backup permissions verified as 0700/0600; fresh
Chromium login passed for the selected user/database following the controlled
Odoo reload. No sales were submitted.

Sales suite validation: all eleven cases ran against the selected dev database;
nine passed UI, backend pricing and pre-submit checks. Both eligible combined
contract/promotion cases failed because the UI clears/hides the promotion. Every
final-run draft was removed through the scoped Odoo draft API. See
`validation_results.json` for the preserved report path and coverage limits.
