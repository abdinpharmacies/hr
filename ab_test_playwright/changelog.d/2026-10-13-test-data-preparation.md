# Test data preparation and sales UI runner

## a4c813f4b — emadco88 — 2026-10-13

Original commit subject: `ab_test_playwright/ NEW test automation script`

- Add standalone preparation tools, restricted backups and login verification for the selected development records.
- Add eleven reusable JSON scenarios and a visible/headless preview runner with UI and backend pricing checks.
- Document preview-only submission and preserve the initial nine passing and two failing case results.

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

## 939c058e0 — emadco88 — 2026-10-14

Original commit subject: `ab_test_playwright/sales_ui_cases.json FIX JSON file`

- Restore valid JSON at the start of the scenario file.

Files changed:

- `ab_test_playwright/sales_ui_cases.json`

## Current changes before commit:

- Register case-step actions centrally and expose `--list-actions`; reject unknown actions and invalid submit sequences before login.
- Add explicit normal UI submission with one click, bounded status checks and no automatic retry.
- Verify saved invoice identity, lines, prices, contract/promotion, shortage reasons and totals.
- Preserve submitted/uncertain bills and block following cases on unresolved or rejected submissions; retain the existing single-login preview workflow.
- Document action usage and add isolated browser simulations for submission and saved-record validation.
- Keep all bundled cases preview-only and distinguish simulated verification from the earlier live preview results.

Files changed:

- `ab_test_playwright/actions.json`
- `ab_test_playwright/submission.mjs`
- `ab_test_playwright/selftest_submission.mjs`
- `ab_test_playwright/run_sales_ui.py`
- `ab_test_playwright/sales_ui_runner.mjs`
- `ab_test_playwright/sales_ui_cases.json`
- `ab_test_playwright/README.md`
- `ab_test_playwright/validation_results.json`
- `ab_test_playwright/changelog.d/2026-10-13-test-data-preparation.md`

Validation: isolated Chromium simulations passed saved, rejected, pending, lost-response
and timeout cases, verified one submit click and rejected repeat attempts, and checked
saved-record mismatch detection. Registry/handler matching and launcher validation passed.
The live preview rerun was blocked by connection refusal at port 4050; no invoices were
posted. The blocked report path and simulation command are in `validation_results.json`.
