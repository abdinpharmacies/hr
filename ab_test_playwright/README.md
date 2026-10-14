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
checks and shortage handling. The runner also supports explicit normal submission.

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

The runner logs into Odoo once and enters the employee PIN once per run, keeping
one browser page and employee session for all selected cases. Each case uses an
empty bill slot; existing user bills are preserved. It turns off stock
filters, searches/adds the selected products, changes quantities, chooses
contracts/promotions, and compares UI totals with independent JSON expectations
and real Odoo backend pricing responses. On shortage lines it selects **Other**
and enters **Development UI test**. It opens and fills the pre-submit dialog,
then goes Back. After each case it removes only its own unsubmitted draft through
the UI and waits for the slot to become available, allowing all eleven cases to
run without filling the ten slots. Ordinary assertion failures still allow the
next case to run. Cleanup failure or session expiry blocks remaining cases; the
runner never automatically logs in or enters the PIN again. It closes the employee
session and browser once at the end. Reports include login counts and draft IDs.

**The bundled cases remain preview-only.** `PASS_PREVIEW` verifies UI, backend
quote and dialog behavior, not saved invoices or E-Plus posting. There is no fake
E-Plus environment in normal runs; stock reads use the configured backend.

### Registered actions and normal submission

List all supported case-step actions without logging in:

```bash
/opt/odoo19/venv19/bin/python ab_test_playwright/run_sales_ui.py --list-actions
```

`actions.json` registers the supported names. Unknown actions and invalid submit
sequences are rejected before credentials or browser startup. To submit a case,
replace its final `submit_or_preview` step with `submit`:

```json
[
  { "action": "prepare_submission" },
  { "action": "submit" },
  { "action": "assert_saved_invoice_if_submitted" }
]
```

This is the end of the case's `steps` array, after product/pricing checks. An
explicit `submit` clicks normal **Submit (F10)** once and follows the configured
Odoo/E-Plus posting flow even though `defaults.execution_mode` remains `preview`.
The default controls the existing preview workflow; `submit_or_preview` still
screenshots the dialog and clicks Back. No extra confirmation is requested.

The runner checks submission status for up to 60 seconds (an in-flight status
request may take up to 10 additional seconds). It never automatically resubmits.
`PASS_SUBMITTED` requires confirmed saved status and successful backend checks:
invoice identity, branch/customer/employee, contract/promotion, quantities, unit
prices/UoM, shortage reasons and totals. Pending is not a pass; pending, rejected,
prepending or unknown outcomes retain the bill and block subsequent cases.
Reports contain invoice IDs, client tokens, external references and protected
draft IDs for review. Submitted and uncertain bills are never discarded by cleanup.

Run the isolated simulation checks without Odoo or E-Plus:

```bash
PLAYWRIGHT_BROWSERS_PATH=/opt/playwright/browsers node ab_test_playwright/selftest_submission.mjs
```

These simulate submission responses in a local browser fixture; they do not prove
real invoice posting. The implementation's real preview rerun was blocked because
Odoo at port 4050 was offline. No real submit was performed during verification.

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

Last successful live preview validation (before adding submit): **11 passed**, with exactly one Odoo login and one employee
PIN login across all cases. All eleven distinct test drafts were cleaned up and
the employee session closed. The two previously failing combined promotion cases
now pass against the current development application with unchanged expectations.
See `validation_results.json` for case coverage and the full report location.
