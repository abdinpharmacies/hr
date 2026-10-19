# Development test data preparation

Standalone tooling, not an Odoo addon. It does not import or install `ab_sales_test`.

## Browser prerequisites

The browser scripts load `@playwright/test` and `playwright` from `/opt/playwright`.
Install the shared dependency and its Chromium browser once before running them:

```bash
npm install --prefix /opt/playwright --save-exact @playwright/test@1.64.1
PLAYWRIGHT_BROWSERS_PATH=/opt/playwright/browsers /opt/playwright/node_modules/.bin/playwright install chromium
```

The account running these commands must have write access to `/opt/playwright`.
The sales launcher sets `PLAYWRIGHT_BROWSERS_PATH` automatically. Headed runs
require an active desktop display. Package installation alone does not install
the Chromium binaries. See the [Playwright browser setup documentation](https://playwright.dev/docs/browsers).

## Test record preparation

Preview the fixed development record selection:

```bash
/opt/odoo19/venv19/bin/python ab_test_playwright/prepare_test_data.py
```

Apply the labels and enter the new Odoo password at the hidden prompt:

```bash
/opt/odoo19/venv19/bin/python ab_test_playwright/prepare_test_data.py --apply
```

Both preparation scripts default to `odoo19-POS.conf` in the project root and
ask for the database name when `--db` is omitted. For unattended execution, pass
`--db 'abdin_replica(POS)'` explicitly. Use `--config` for another configuration.
They connect directly to PostgreSQL and do not require an Odoo URL. Without
`--apply`, both scripts remain read-only previews.
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

`sales_ui_cases.json` contains fifteen reusable scenarios using your fixed record
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

The sales launcher asks for the Odoo URL and database name on each interactive
run unless supplied with `--url` and `--db`. Neither value has a default or is saved
to the scenario JSON. For example, enter `http://127.0.0.11:4093` and
`abdin_replica(POS)` at the prompts. Database names are preserved exactly.

To supply the connection settings explicitly:

```bash
/opt/odoo19/venv19/bin/python ab_test_playwright/run_sales_ui.py \
  --url http://127.0.0.11:4093 \
  --db 'abdin_replica(POS)' \
  --headed --case CASH
```

The sales launcher's `--config` defaults to `odoo19-POS.conf` in the project root,
resolved independently of the current directory. Use `--config` to select another
Odoo configuration containing the PostgreSQL connection settings. The preparation
scripts use the same configuration default and also prompt for the database;
launching tests does not apply fixtures or reset passwords.

Only HTTP/HTTPS localhost or loopback origins are accepted, including `127.0.0.11`
and `[::1]`. Do not include credentials, a page path, query parameters or a fragment
in the URL. The browser runner and login verifier share the local-address check.

For unattended runs, supply `--url`, `--db`, `--headed` or `--headless`, and
`AB_TEST_PASSWORD` and `AB_TEST_PIN` through the environment. Missing connection
arguments fail before authentication or database access. `--help` and
`--list-actions` do not prompt for connection settings. Existing login identity,
test records and expected values must still match the selected database.
The configured employee access profile must have `pos_allow_login` enabled;
otherwise the launcher stops before browser startup. An authorized POS HR manager
can review this setting under POS HR → Configuration → Employees. The tooling
does not enable login or change permissions. Browser setup failures record their
actual setup stage, such as `select_employee`, instead of `new_empty_bill`.
Use `--suite` for a compatible JSON file and repeat `--case` to select several
scenarios. Unknown actions fail explicitly.

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

Draft tracking reads the current tab's user/employee-scoped `sessionStorage`
workspace and selection. Empty Ready bills are local-only, so creation does not
wait for `pos_save_draft_cache`. Each case explicitly creates a bill and claims
only its new token; existing bills and shared fallback cache entries are not
claimed. Cleanup clicks Remove once and waits for that token to leave the tab
workspace, supporting both local Ready removal and server-backed draft removal.

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
| CASH | 380.00 |
| CONTRACT_25 | 95.00 |
| CONTRACT_0 | 0.00 |
| CONTRACT_100 | 353.40 |
| PROMO_ONLY | 125.00 |
| PROMO_MIXED | 225.00 |
| PROMO_THEN_CONTRACT | 380.00 |
| CONTRACT_THEN_PROMO | 380.00 |
| CONTRACT_CLEAR_NO_AUTO_PROMO | 380.00 |
| PROMO_QTY_UPDATE | 350.00 |
| PROMO_THEN_DISCOUNTED_CONTRACT | 95.00 |
| CONTRACT_MANUAL_PROMO | 225.00 |
| CONTRACT_CHANGE_CLEARS_MANUAL_PROMO | 380.00 |
| CONTRACT_CLEAR_MANUAL_PROMO | 225.00 |
| CONTRACT_MANUAL_PROMO_QTY_UPDATE | 350.00 |

Both products are local. Prices are pinned at 100 and 280 and checked before
testing; price drift is a failure, not a reason to silently change expectations.
Mixed-product and promotion-quantity cases explicitly select promotion 2 before
checking totals, so other available promotions do not prevent the intended offer
from being applied. Contract 2 must be permitted for store 104; preparation does
not change contract store permissions. If a session locks, remaining cases stay
blocked rather than automatically entering the PIN again.
Contract-affected bills require explicit promotion selection. New cases assert no
selected/applied chip and payment of 380 before clicking, then verify payment of
225 after the click. Contract changes exercise 4 → 1 → 4 using existing fixtures;
quantity updates retain the manual selection and produce payment of 350.
`CONTRACT_CLEAR_RESTORES_PROMO` was renamed `CONTRACT_CLEAR_NO_AUTO_PROMO`;
update any saved `--case` commands accordingly.

The runner waits for browser RPCs to finish and a 700 ms quiet period covering
the current 300/350 ms pricing debounces before checking pricing. UI-total steps
may provide an inline `expected` object for intermediate totals; final checks use
the case expectations. `select_promotion_manually` always clicks and rejects an
already selected/applied chip. `assert_promotion_unselected` requires an available
chip with no selection; `assert_promotion_applied` verifies the applied chip.
Combined backend checks pass store, customer, and explicit selection through
`pos_contract_totals`. All fifteen cases remain preview-only.

The old reference
invoice totals and its 10% promotion are not applicable to this fixed-price suite.

Historical live preview validation covered the original eleven cases only.
`validation_results.json` records that earlier run, not verification of the expanded
suite. Rerun the suite with runtime credentials to validate the fifteen cases.

Product 74542 now uses an expected unit price of 100.00. Historical validation
reports used 1.00 and do not validate the revised expectations. Database prices
are not modified by this scenario update.
