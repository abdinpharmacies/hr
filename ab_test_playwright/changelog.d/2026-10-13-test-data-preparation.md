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

## Current changes before commit:

- Authenticate Odoo and the employee once per suite, retaining the same browser page and session for every case.
- Start each case with an empty run-owned bill and remove only its preview draft through the UI, freeing slots for reuse.
- Preserve separate case results, attribute RPC errors to their initiating case, and report login counts and draft cleanup.
- Continue after assertion failures; block remaining cases if cleanup fails or the session expires instead of reauthenticating.
- Close the employee session once at suite completion and document the shared-session workflow.
- Refresh validation: all eleven cases pass in the current application with unchanged JSON expectations; the two earlier combined promotion failures no longer reproduce.

Files changed:

- `ab_test_playwright/README.md`
- `ab_test_playwright/sales_ui_runner.mjs`
- `ab_test_playwright/validation_results.json`
- `ab_test_playwright/changelog.d/2026-10-13-test-data-preparation.md`

Validation: Node syntax and Git whitespace checks passed. The full headless suite
passed eleven cases with one Odoo login, one employee login and eleven distinct
cleaned drafts. A temporary two-case suite deliberately failed the first total
assertion and passed the next case in the same session; both drafts were cleaned.
A read-only PostgreSQL check confirmed no drafts remained for the test employee.
No invoices were submitted. Report paths are retained in `validation_results.json`.
