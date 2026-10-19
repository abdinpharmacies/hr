## f1f22aa0f1d00d5999049f6596918f6133f2de2d - emadco88 - 2026-10-18 13:28:10 +0300

Original commit subject: ab_test_playwright/ FIX make it compatible with new POS

- Adapt sales UI automation to the updated POS draft workspace.

Files changed:

- ab_test_playwright/README.md
- ab_test_playwright/changelog.d/2026-10-18-draft-workspace.md
- ab_test_playwright/draft_workspace.mjs
- ab_test_playwright/sales_ui_runner.mjs

Current changes before commit:

- Ask for the Odoo URL and database on interactive sales runs unless supplied through command-line arguments; reject missing unattended inputs before authentication or database access.
- Default the sales launcher configuration to the project's odoo19-POS.conf, with an explicit --config override.
- Use the project configuration in both preparation scripts and prompt for the database when omitted; preserve explicit overrides and read-only preview defaults.
- Accept local HTTP/HTTPS loopback origins, including 127.0.0.11, through shared browser validation and matching launcher checks.
- Preserve database names exactly and remove unused connection defaults from the scenario JSON.
- Document interactive and unattended execution; retain existing credentials, fixture validation and preview behavior.
- Set product 74542's expected unit price to 100.00 and recalculate affected cash, contract, promotion and intermediate UI totals. Update the documented payment table without changing database prices or historical validation reports.
- Document shared Playwright/Chromium installation and align the simulated saved-invoice fixture with the revised cash total of 380.00.
- Reject employee profiles with POS login disabled before browser startup and identify the actual authentication/setup stage in blocked-case reports.
- Explicitly select promotion 2 in PROMO_MIXED and PROMO_QTY_UPDATE before checking totals when multiple offers are available; preserve existing price expectations and branch/session restrictions.

Files changed:

- ab_test_playwright/README.md
- ab_test_playwright/connection.mjs
- ab_test_playwright/prepare_sales_scenarios.py
- ab_test_playwright/prepare_test_data.py
- ab_test_playwright/run_sales_ui.py
- ab_test_playwright/sales_ui_cases.json
- ab_test_playwright/sales_ui_runner.mjs
- ab_test_playwright/verify_login.mjs
- ab_test_playwright/selftest_submission.mjs
- ab_test_playwright/changelog.d/2026-10-18-runtime-connection.md

Verification:

- Passed 29 isolated Python input/CLI checks and 18 JavaScript URL/encoding checks, including interactive inputs, overrides, missing unattended arguments, loopback acceptance, remote-address rejection, and database names containing parentheses.
- Passed 11 additional isolated preparation-script checks for prompts, configuration defaults, explicit overrides, missing/blank database inputs, help and end-of-input handling. No database connections were made during these checks.
- Independently recalculated all 15 final and 10 intermediate expectation sets with decimal arithmetic for the 100.00 price. Confirmed all scenario steps, quantities, contract/promotion fixtures and preview-only behavior remain unchanged. Live browser validation of the new price expectations was not run.
- Installed @playwright/test 1.64.1 and matching Chromium, headless shell and FFmpeg under /opt/playwright. A visible local-page browser/assertion check passed; the isolated submission self-test passed all seven reported groups, including five submission outcomes, saved-invoice checks and action registration. These checks made no Odoo or E-Plus requests. Playwright used its Ubuntu 24.04 fallback browser build for this OS.
- Python parsing, JavaScript syntax, scenario JSON parsing and git diff --check passed.
- Inspected report 20261019T065857689261Z: contract 2 was rejected for store 104; mixed-product screenshots required manual promotion selection; later cases lost the employee session. Verified the two corrected action sequences, unchanged expectations, registered actions and preview-only behavior across all 15 cases. Live rerun remains outstanding; contract access and session loss were not changed.
- On 2026-10-19, read-only ORM diagnosis under the test user's permissions confirmed profile 1 has pos_allow_login=False and is absent from the login-enabled dropdown search. Passed three isolated preflight cases for disabled, null and enabled login flags. No permissions were changed.
- No live Odoo browser suite, fixture writes or invoice submissions were performed. This standalone tooling change adds no Odoo UI strings or translation entries.
