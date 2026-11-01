# Validation evidence — 2026-10-29

Only isolated PostgreSQL databases were modified. No production upgrade, external
SQL write, service restart, commit or deployment was performed.

## Environment

- Python: `/opt/odoo19/venv19/bin/python`
- Odoo: `/opt/odoo19/server/odoo-bin`, 19.0
- Addons: `/opt/odoo19/server/addons,/opt/odoo19/custom-addons`
- Isolated config/data: `/tmp/supplier_claim_test.conf`, `/tmp/supplier_claim_validation_data`
- HTTP/gevent: 5069/5072 and 5169/5172; workers 0; cron threads 0.
- Chrome browser tests used `websocket-client==1.8.0` installed only under
  `/tmp/supplier_claim_test_dependencies`; the application venv was unchanged.

## Results

| Check | Evidence |
|---|---|
| Clean installation of core and supported Telegram adapter | `supplier_claim_release_20261029`; installation completed with registry, views and security loaded |
| Final core + Telegram + HTTP/browser suite on fresh-origin DB | 43 tests, 0 failures, 0 errors; `/tmp/supplier_claim_delivery_pass.log` |
| Final core + HTTP/browser suite on restored/migrated DB | 30 tests, 0 failures, 0 errors; `/tmp/supplier_claim_upgrade_complete.log` |
| Real HTTP binary downloads | All four document types for all eight roles on closed, archived claims: 32 successful byte comparisons |
| English and Arabic browser forms | Passed in both final suites; registered action URL and Arabic amount label verified |
| Arabic | English/Arabic form labels tested; both catalogs passed `msgfmt --check-format`; real Arabic browser and tax-selection checks passed (2 targeted tests, `/tmp/supplier_claim_arabic_verified.log`) |
| Legacy migration | Eight synthetic legacy states, unchanged amount totals, supplier bytes/filenames, historical states and logged continuity exceptions verified |
| Legacy Bank Accounts continuation | Approved to Ready to Close without a fabricated payment request, then rolled back |
| Invalid migration | Real upgrade stopped on invalid synthetic claim ID 1; original module version, schema and other seven values remained unchanged |
| Backup restoration | `/tmp/supplier_claim_before_upgrade.dump` restored all eight original claims to `supplier_claim_restored_20261029` |
| Company migration | Single-company assignment and mandatory explicit XML-ID mapping with multiple companies tested |
| Static checks | Python AST, XML parsing, gettext format checks and `git diff --check` |

Odoo's statistics counters also include class setup/teardown. Counts above use the
final `odoo.tests.result` test totals. Earlier exploratory runs exposed defects and
were superseded by the passing delivery logs.

## Reproduction

Run the README command with `-i` on an empty isolated DB. Repeat with `-u` on a
restored legacy database. Use `--test-tags=/ab_supplier_claim_cycle` when the
optional adapter is absent. Do not use `--no-http` for the HTTP/browser suite.

`tests/migration_rehearsal.py` supplies `seed_legacy(env)` and
`verify_upgraded(env)` for an isolated Odoo shell. Seed using the original
19.0.4.2.1 addon, commit the synthetic fixtures, take a backup, then run the targeted
upgrade and verify using the new addon. The verifier exercises the Bank Accounts
continuation: roll back after verification to preserve fixture states. The automated
suite additionally tests invalid parsing, no partial conversion and company mapping.

## Deployment checks and limits

- Validation used synthetic fixtures, not a supplied production backup. Rehearse
  against the actual backup before authorizing production deployment.
- Multi-company upgrades must supply the reviewed claim-to-company XML-ID mapping.
  Branch isolation uses native company scope. Legacy area labels are not branch ACLs.
- `ab_supplier_claim_cycle_telegram` is tested with mocked delivery. No real Telegram
  delivery or external SQL connection is required by these tests.
- The older `ab_supplier_claim_workflow_telegram` has pre-existing references to
  absent models and an absent form field. It remains unsupported, as documented
  in the README; it was not modified or installed.
- Existing dependency addons emit unrelated manifest/label warnings. They were
  not changed as part of this task.
- Production packaging should exclude development tests, fixtures and caches while
  retaining the versioned migration scripts needed for this supported upgrade.

## Modified files

- `models/ab_supplier_claim_cycle.py`: workflow, amounts, company scope, permission
  checks, preparation, returns and version-linked document replacement.
- `models/payment_preparation.py`, `models/stage_history.py`, `models/__init__.py`:
  immutable document records, company SLA setting, expanded immutable history.
- `security/groups.xml`, `security/record_rules.xml`, `security/ir.model.access.csv`:
  Tax role, scoped global visibility and document ACLs.
- `views/parallel_workflow.xml`, `wizard/claim_decision.py`,
  `wizard/claim_decision_views.xml`: unified form, queues, return/replacement dialogs.
- `migrations/19.0.5.0.0/pre-migrate.py`, `post-migrate.py`: validated amounts,
  company assignments, attachments, state/resume mapping and continuity audit.
- `i18n/ar.po`, `i18n/ar_001.po`: preserved translations plus new terms/references.
- `tests/test_claim_cycle.py`, `test_claim_http.py`, `migration_rehearsal.py`,
  `tests/__init__.py`: current workflow/security/migration/browser coverage.
- Manifest, README, this report and changelog: version/dependencies and delivery instructions.
- Supported Telegram adapter manifest, model, tests and changelog: parallel routing,
  company/read filtering, preparation notifications and corrected action URLs.

Git index contents were preserved. Final README/report and migration-test fixture
adjustments may remain unstaged; include them when preparing a later commit.

## XML developer-mode regression — 2026-10-29

Three compact view definitions lacked text before their first architecture child.
The installed Odoo file loader concatenates `field_arch.text` with child XML, which
fails when that text is `None`. Added XML whitespace in `parallel_workflow.xml`
and `claim_decision_views.xml`, preserving the view definitions and XML IDs.
A targeted isolated upgrade with `--dev=xml` and a regression test invoking
`get_view_arch_from_file` for every module view passed: 1 test, 0 failures/errors.
Log: `/tmp/supplier_claim_dev_xml.log`. The deployment copy requires separate
approval; automatic review rejected modifying that running deployment tree.

## Original design preserved — 2026-10-29

Removed the whole-form replacement from `invoice_form_parallel_workflow` and
extended the original inherited design instead. The original
`views/claim_design.xml`, `views/supplier_terms.xml` and
`views/ab_supplier_claim_cycle.xml` remain byte-for-byte unchanged from HEAD.
Existing SCSS colors, panels, radii, shadows, notes and exception-history styling
are retained; a scoped addition stacks the two parallel department pairs.

The new Tax, preparation, amount and revision controls use the existing boxes and
colors. Department-specific action labels distinguish simultaneous reviews.
Existing list colors now follow the new state names after the original color view.

- Full core and supported Telegram suite with `--dev=xml`: **45 passed**, no failures
  or errors (`/tmp/supplier_claim_design_final.log`).
- Final design/list-color and XML-loader checks: **2 passed**, no failures or errors
  (`/tmp/supplier_claim_design_list_check.log`).
- English and Arabic browser screenshots inspected; preparation timeline label
  verified in Arabic. Both catalogs pass gettext format checks.
- Workspace implementation only. The separate running deployment copy was not
  changed, and no production upgrade or service restart was performed.

Previews:
- English: `/tmp/odoo_tests/supplier_claim_release_20261029/screenshots/supplier_claim_design_20261029_134924_704807_TestClaimHttp.png`
- Arabic: `/tmp/odoo_tests/supplier_claim_release_20261029/screenshots/supplier_claim_design_20261029_134920_038299_TestClaimHttp.png`
