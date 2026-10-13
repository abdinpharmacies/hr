# Development test data preparation

Standalone tooling, not an Odoo addon. It does not import or install `ab_sales_test`.

Preview the fixed development record selection:

```bash
/opt/odoo19/venv19/bin/python ab_test_playwright/prepare_test_data.py
```

Apply the labels and enter the new Odoo password at the hidden prompt:

```bash
/opt/odoo19/venv19/bin/python ab_test_playwright/prepare_test_data.py --apply
```

Defaults: `--config /opt/odoo19/config/replica19.conf --db abdin_replica19`.
For automation, supply the password through `AB_TEST_PASSWORD` (or the variable
named by `--password-env`), never in a committed file.

The script prefixes names once with `[TEST]` for products/cards 74542 and 94123,
customer 19934, promotion 2, contracts 1–4, store 104, employee 668 (access
profile 1), and partner 2455 (user 2452). It preserves the login name, employee
PIN, identifiers, permissions, pricing and inventory values.

All writes use parameterized PostgreSQL in one transaction. The password is
hashed with Odoo's PBKDF2-SHA512 algorithm and at least 600,000 rounds, respecting
the database's higher configured work factor. Exact row counts and values are
checked before commit. Repeating the script does not duplicate name prefixes;
it creates another backup and resets the password again.

Original and resulting field values, including password hashes, are saved to
`backups/` before updates. The directory is mode 0700, files are mode 0600, and
Git ignores them. These backups are sensitive and are not full database backups.
For a bounded manual restore, use the saved `before` values only after confirming
the current values still match `after`; do not overwrite subsequent user edits.

Direct SQL does not invalidate existing Odoo process caches. Refresh the target
server through a controlled restart, then verify in a fresh browser context.
The script itself does not stop any Odoo process.

`verify_login.mjs` uses the shared Playwright installation in `/opt/playwright`
and verifies login in a fresh headless Chromium context. Supply a JSON object on
stdin with `url`, `database`, `login`, `password`, and `expectedUserId`, and set
`PLAYWRIGHT_BROWSERS_PATH=/opt/playwright/browsers`. It accepts only a local URL,
checks the authenticated database/user and `[TEST]` display name, and closes the
browser. It does not save credentials, screenshots, or authenticated state.

## Sales UI scenarios

`sales_ui_cases.json` contains eleven reusable scenarios using your fixed record
IDs. It includes setup requirements, UI steps, exact expected totals, backend
checks, shortage handling, and a final-posting specification for a future runner.

Contracts 1, 2 and 3 reproduce the reference JSON's 25%, 0% and 100% customer
contributions and origin discounts, with Allow Promotions disabled. Contract 4
uses 100% copay, zero discounts/cap, and Allow Promotions enabled to satisfy the
running backend's combined-pricing requirements. Promotion 2 retains fixed price 125; its date
restrictions are removed for testing. Original values are backed up.

```bash
# Preview fixture configuration (no writes)
/opt/odoo19/venv19/bin/python ab_test_playwright/prepare_sales_scenarios.py

# Apply the fixture configuration if needed; already applied for this delivery
/opt/odoo19/venv19/bin/python ab_test_playwright/prepare_sales_scenarios.py --apply

# Run the UI suite; asks visible/headless, Odoo password, and employee PIN
/opt/odoo19/venv19/bin/python ab_test_playwright/run_sales_ui.py

# Run one case visibly, or all cases headlessly
/opt/odoo19/venv19/bin/python ab_test_playwright/run_sales_ui.py --headed --case CONTRACT_25
/opt/odoo19/venv19/bin/python ab_test_playwright/run_sales_ui.py --headless
```

For unattended runs provide `AB_TEST_PASSWORD` and `AB_TEST_PIN` through the
environment. Config/database defaults match the preparation script; `--url`
defaults to `http://127.0.0.1:4050`. Use `--suite` for a compatible JSON file and
repeat `--case` to select several scenarios. Unknown actions fail explicitly.

The runner logs in through the UI, starts an employee session, turns off stock
filters, searches/adds the selected products, changes quantities, chooses
contracts/promotions, and compares UI totals with independent JSON expectations
and real Odoo backend pricing responses. On shortage lines it selects **Other**
and enters **Development UI test**. It opens and fills the pre-submit dialog,
then goes Back. It tracks draft IDs created by its own browser, discards those
through Odoo's draft API, and closes its employee session. A temporary cache-lock
conflict is retried only for this idempotent cleanup operation.

**This runner is preview-only: it never clicks the final Submit (F10).** A
`PASS_PREVIEW` verifies UI, backend quote and dialog behavior, not saved invoices
or E-Plus posting. The JSON includes future saved-invoice checks, explicitly
reported as `NOT_EXECUTED`. There is no fake E-Plus environment; stock reads use
the configured backend. Do not interpret this as end-to-end posting validation.

Reports and screenshots are written beneath
`/opt/playwright/artifacts/replica_addons/sales_suite/<run timestamp>/`.
Failures return a nonzero exit status. Credentials are not included in reports.

| Case | Expected customer payment |
|---|---:|
| CASH | 281.00 |
| CONTRACT_25 | 70.25 |
| CONTRACT_0 | 0.00 |
| CONTRACT_100 | 261.33 |
| PROMO_ONLY | 125.00 |
| PROMO_MIXED | 126.00 |
| PROMO_THEN_CONTRACT | 126.00 |
| CONTRACT_THEN_PROMO | 126.00 |
| CONTRACT_CLEAR_RESTORES_PROMO | 126.00 |
| PROMO_QTY_UPDATE | 251.00 |
| PROMO_THEN_DISCOUNTED_CONTRACT | 70.25 |

Both products are local. Prices are pinned at 1 and 280 and checked before
testing; price drift is a failure, not a reason to silently change expectations.
The combined cases expect promotions with an eligible contract; discounted
contracts should still clear promotions. The running backend exposes `allow_promotions`,
although the local source inspected did not declare it. These scenarios target
the running application and will fail explicitly if that capability is missing.
The old reference
invoice totals and its 10% promotion are not applicable to this fixed-price suite.

Latest validation: **9 passed, 2 failed**. `PROMO_THEN_CONTRACT` displays net
281.00 instead of 126.00, and `CONTRACT_THEN_PROMO` cannot find the promotion
control after selecting contract 4. These are retained as failing regression
cases; the suite does not silently accept the incorrect combination behavior.
See `validation_results.json` for case coverage and the full report location.
