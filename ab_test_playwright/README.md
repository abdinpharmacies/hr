# Callcenter Playwright tooling

Standalone development tooling implemented directly in the Callcenter checkout.
This is not an installable Odoo addon and does not require a module upgrade.
It exercises the same 15 sales scenarios and 21 actions as the POS reference,
using Callcenter employee sessions, draft ownership, local invoice records,
recorded promotion totals, and Branch API submission identities.

Employee login may initially select Odoo's default allowed branch. The runner
checks the employee, access profile, service user, and active session at login,
then selects the requested branch in the New Bill dialog. It verifies the
session branch and the new draft before entering customer or product data.
Denied branch switches and identity mismatches fail the case. Reports include
expected/actual identity IDs and failing HTTP resource paths, without session
tokens. Page and translation errors remain failures and are reported separately
from employee authentication errors.

Login redirects directly to the selected Sales action. The runner avoids
reloading that action after login so in-flight response bodies remain available
to Playwright. Genuine HTTP, RPC, and unreadable-response failures still block
the run.

## Check the installation

Run from the Callcenter repository root:

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/run_sales_ui.py --validate
/opt/odoo19/venv/bin/python ab_test_playwright/run_sales_ui.py --list-cases
/opt/odoo19/venv/bin/python ab_test_playwright/run_sales_ui.py --list-actions
/opt/odoo19/venv/bin/python ab_test_playwright/selftest_cli.py -v
/opt/odoo19/venv/bin/python ab_test_playwright/selftest_terminal.py -v
/opt/odoo19/venv/bin/python ab_test_playwright/selftest_parity.py -v
node ab_test_playwright/selftest_submission.mjs
```

These commands do not authenticate to Odoo, change fixtures, or submit invoices.
The JavaScript self-test launches actual headless Chromium against an intercepted
local page and simulated status responses. It does not prove business posting.
Browser launch requires an environment that permits Chromium subprocesses.

The installed Node packages are read from `/opt/playwright/node_modules` and
Chromium from `/opt/playwright/browsers`. No npm installation is needed in this
directory. Headed runs need a working desktop display.

## POS feature parity

All 15 POS scenarios now retain their full ordered steps, intermediate totals,
final expectations, contract terms, fixed-price promotion, and shortage policy.
Record IDs are resolved through the selected Callcenter product/contract aliases.
`pos_reference.json` captures the POS reference; the parity self-test detects
missing steps, changed expectations, fixture drift, or missing action handlers.
To also check the current POS checkout without changing either branch:

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/selftest_parity.py \
  --pos-root /opt/odoo19/custom-addons-pos19/ab_test_playwright -v
```

| POS capability | Callcenter implementation |
|---|---|
| Terminal connection and credential questions | URL, database, mode, login, searchable records, hidden password/PIN |
| Fixture labels and optional password reset | ORM preparation with explicit `--apply`; reset also needs `--reset-password` |
| Contract/promotion preparation | Same contract terms; promotion settings checked and dates prepared |
| Fresh browser login verifier | Same user/database and `[TEST]` name checks |
| 15 scenarios and 21 registered actions | All POS steps and intermediate/final expected amounts retained |
| Pricing and backend checks | Business RPCs settle; explicit selected/applied promotion checks and stored quote |
| Shortage handling | Other / Development UI test; saved-line reason checks |
| Preview and explicit submission | Preview default; submit action plus `--allow-submit`; one click and status reconciliation |
| Saved invoice validation | Identity, lines, units, prices, totals, shortages plus Callcenter Branch identity and frozen promotion snapshot |
| Reports and screenshots | Login counts, checkpoints, quotes, submitted invoice IDs, draft ownership and failure images |
| Submission simulations | Saved/rejected/pending/lost-response/timeout Chromium fixtures and mismatch checks |
| Cleanup | Remove only run-owned unsubmitted drafts; retain attempted invoices; close session |

Runtime adaptations remain explicit: Callcenter uses its local invoice and
Branch API status contract, configurable records, and private local reports.
The source POS checkout and its commits are unchanged. No database preparation,
password reset, promotion deletion, or real submission runs as part of the parity checks.

## Run with terminal questions

No Nano, copied JSON, or prefilled record IDs are needed for an interactive run:

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/run_sales_ui.py
```

Answer the URL, database, visible/headless mode, and Odoo login questions. The
script lists matching employee access profiles, verified branches, customers,
products, contracts, and promotions. Enter a record ID, type a name to search,
or press Enter to accept a displayed default. Enter `q` or press Ctrl+C to cancel.
Invalid input can be corrected in the terminal. User IDs, employee IDs, codes,
external serials, and units are resolved from the chosen records automatically.

After read-only fixture checks pass, enter the Odoo password and employee PIN
at hidden prompts. The runner then starts the browser. Answers are kept in
memory for this run and recorded only as non-secret report metadata; the
template and existing local JSON are not overwritten. Passwords and PINs are
never written to reports or configuration files.

Existing configured suite values remain usable as selection defaults. For a
preview, the selected Odoo user and branch need not have `[TEST]` names, but
all existing access checks and labelled financial QA fixture checks still apply.
Explicit posting additionally requires a labelled QA user contact and branch.
No names, permissions, prices, or fixture values are changed by startup.

When `--suite` points at a `reports/.../selected-suite.json` snapshot, only its
record selections, login settings, and QA database are reused. Cases and fixture
expectations come from the current bundled suite, including all restored POS
checks. Thus old saved report commands run the current scenarios; omit `--case`
to run all 15. Explicit custom suite files outside `reports/` keep their own cases.

To test one case or run without a visible browser, add `--case CASH` or
`--headless`. The remaining missing settings are still asked interactively.

## Optional saved QA suite

Copy `sales_ui_cases.json` to `sales_ui_cases.local.json` and edit the local copy.
Local suite files are ignored by Git. This is optional for unattended execution
or reusable defaults; interactive setup also works with the blank template.

Set:

- `qa_database`: the exact QA Callcenter database name.
- `credentials.login`: the intended Odoo service login.
- `records.user_id`, `employee_id`, `employee_access_id`, `store_id`,
  `customer_id`, and `promotion_id`.
- The branch code/external serial and customer code.
- Distinct IDs for `contract25`, `contract0`, `contract100`, and `contractPromo`.
- Product IDs, codes, external serials, and default UoM IDs for `base` and `promo`.

The reference cases use two local-origin products with prices **100** and **280**,
and a fixed-price promotion of **125** for `promo` only. Product prices, origin,
units, contract terms, promotion scope, and financial expectations must match;
the runner fails on drift rather than changing prices or recalculating expected
amounts from the system under test. Select dedicated QA records that already
match those prices, or deliberately revise the reference expectations yourself.

Use a fresh QA Callcenter database and a QA Branch provider. The Callcenter
rollout documentation requires a fresh installation for the revised draft schema.
The Odoo login needs Callcenter access, the employee profile must already permit
POS login and sales at the selected branch, and the Branch connection must be
verified with posting permission. Existing access permissions are never enabled
by these scripts. Ensure stable product/customer/contract/promotion references
resolve to the intended records on both databases before enabling submission.

## Optional fixture preparation

Both helpers default to `odoo19-callcenter.conf` in the repository root and use
the same terminal questions when settings or record selections are missing.
Preparation uses the configured Odoo ORM connection and does not request an
employee PIN. Only an explicit password reset asks for a new hidden password.
Use `--config` to select another file.

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/prepare_test_data.py \
  --suite ab_test_playwright/sales_ui_cases.local.json --db YOUR_QA_DATABASE

/opt/odoo19/venv/bin/python ab_test_playwright/prepare_sales_scenarios.py \
  --suite ab_test_playwright/sales_ui_cases.local.json --db YOUR_QA_DATABASE
```

Without `--apply`, these are read-only previews. Explicit `--apply` performs the
displayed bounded operation through Odoo ORM and saves original values first to
`backups/` with directory permissions 0700 and file permissions 0600.
Interactive setup binds the chosen records to the database entered for this run.
For unattended execution, `qa_database` in the supplied suite must exactly match
the selected database and all required settings must already be configured.

`prepare_test_data.py` adds a single `[TEST] ` name prefix to the selected user
contact, employee, branch, customer, promotion, contracts, and product cards.
It refuses product cards shared by other products. It does not change PINs,
prices, inventory, logins, stable identifiers, or permissions. Password reset is
available only through an explicit invocation:

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/prepare_test_data.py --apply --reset-password
```

This resets the selected Odoo login, asks for a hidden new password or uses
`AB_TEST_PASSWORD`, and backs up the old/new password hashes with the label
changes before applying them in one transaction. Hashing uses Odoo's password
scheme with at least 600,000 rounds. Hashes are never printed. Use
`--password-env` to choose another variable or `--backup-dir` for another private
backup location. Plain `--apply` labels records without resetting a password.

`prepare_sales_scenarios.py` applies only the allowlisted contract terms and
promotion dates shown in `fixtures`. Other promotion terms must already match
the reference and are never silently changed. Contracts/promotion must already be
labelled `[TEST]`. It does not broaden promotion membership, change allowed
branches/customers, remove product-specific contract rules, or configure the
remote Branch. These inconsistencies must be resolved explicitly in QA.
Preparation changes only the chosen Callcenter database; separately configure
equivalent QA Branch records if actual submission tests will be used.

Backups record model, record ID, original fields, and requested fields. For a
manual rollback, verify that current values still match the recorded `after`
values and restore only those fields through ORM. Do not overwrite later edits.

## Run preview scenarios

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/run_sales_ui.py \
  --suite ab_test_playwright/sales_ui_cases.local.json \
  --url http://127.0.0.1:4095 --db YOUR_QA_DATABASE --headed --case CASH
```

Omit `--case` for all 15 cases; repeat it to select several. Use `--headless`
instead of `--headed` for background execution. URL/database and browser mode are
prompted if omitted during interactive execution; unattended runs require them.
Use the actual running QA URL; the example port is not a default.
Only HTTP/HTTPS localhost or loopback origins are accepted, without embedded
credentials, application paths, query strings, or fragments.

The launcher resolves interactive record selections and validates fixture
identity using the configured PostgreSQL connection in a read-only transaction.
It then asks for the Odoo password and
employee PIN using hidden prompts. Unattended runs may supply `AB_TEST_PASSWORD`
and `AB_TEST_PIN` through the environment. Credentials are passed to Node through
stdin, never command-line arguments, suite files, screenshots of the login page,
or saved browser authentication state.

The runner creates a fresh browser context and signs in once to Odoo and once
with the employee PIN. It reuses that session for the selected cases. Each case
claims a new empty draft token and removes only its own unsubmitted draft after
the preview. Existing drafts are preserved. Cleanup failure or employee-session
expiry blocks remaining cases without automatic PIN reentry. The run closes
its employee session at the end.

Preview fills the pre-submit dialog and clicks **Back**. It does not click the
final **Submit (F10)** button. Unexpected submission requests are blocked.
`PASS_PREVIEW` means UI/quote/dialog checks passed, not that a Branch invoice was
posted. Stock reads still use the selected QA Branch configuration.

## Explicit QA submission

In a separate local suite, change one case's final `submit_or_preview` action to
`submit`. Keep the preceding `prepare_submission` and final
`assert_saved_invoice_if_submitted` steps. Then add `--allow-submit`:

```bash
/opt/odoo19/venv/bin/python ab_test_playwright/run_sales_ui.py \
  --suite ab_test_playwright/submit.local.json \
  --url http://127.0.0.1:4095 --db YOUR_QA_DATABASE \
  --headed --case CASH --allow-submit
```

The flag alone does not convert preview steps into submissions. Both the JSON
action and flag are required. The runner clicks the final submission button
once, then polls `pos_submission_states` with the employee session token for up
to 60 seconds, plus time spent in the initial click and final bounded read.
It never automatically resubmits, even after a lost response.

`PASS_SUBMITTED` requires confirmed `saved` status, an accessible saved local
Callcenter invoice, matching client token/revision, Branch invoice ID and external
serial, customer/employee/branch, contract/promotion, lines, units, shortage
reasons, and expected amounts. Promotion IDs/discount/net are checked against
the first-submission snapshot. Pending, unknown, rejected, malformed identity,
and timeout outcomes are not successful posting tests. Attempted bills are
protected from cleanup and unresolved outcomes stop subsequent cases.

The suite creates ordinary, non-delivery QA sales. It does not test printer
hardware or send delivery notifications. Those need their separate manual
acceptance checks.

## Scenarios and results

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

Reports and screenshots are stored in ignored, timestamped `reports/` directories
or a new directory selected with `--output`. Reports distinguish setup failure,
blocked cases, assertion failure, cleanup failure, preview passes, and confirmed
submission passes. Passwords, PINs, and employee tokens are redacted from error
messages. Screenshots may contain QA business data and should remain private.
Failures and blocked runs return a nonzero exit status. Interactive preflight
errors are shown in the terminal with an option to review the selections again;
they do not require editing JSON.

`verify_login.mjs` separately accepts a JSON object on stdin with `url`,
`database`, `login`, `password`, and `expectedUserId`. It authenticates in a fresh
headless context, verifies Odoo user/database identity, and closes the browser.
It requires a `[TEST]` display name by default, as POS does. For an explicitly
selected existing Callcenter service user used in preview, `requireTestName:false`
in the stdin object skips only the name check. Output is a JSON PASS summary.
It does not log in an employee or save authentication state.
