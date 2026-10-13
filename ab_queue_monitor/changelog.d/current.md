# ab_queue_monitor

## Implementation record

Author: Mohamed Fawzy
Date: 2026-10-05
Commit: `acb020636768e7edbc6a285b0216efa7f86d0266`
Original subject: `ab_queue_monitor/feat: add job discovery and execution dashboard`

- Discover installed-addon background work through bounded AST scans, queue
  declarations, existing schedules and runtime evidence. Scan only on an
  administrator's Discover/Resume action; keep history and differential results.
- Monitor Integration Queue and the dedicated website-sync store without copying
  payloads or modifying queue records. Show idle classification controls and
  link actual checkpoint executions to their classification run counters.
- Provide a responsive dashboard, server-side filters, definition/source views,
  live execution details, database-lease runner evidence and Arabic RTL support.
- Restrict discovery to administrators, protect error details, withhold payload
  values, and preserve business-model access checks on contextual links.
- Include tests and inspected-architecture documentation; provide runtime-only
  packaging without tests or bytecode.
- Fix Discovery History and job definition views in Odoo XML development mode
  by preserving whitespace before each architecture root. Add a regression
  check using Odoo's source-view loader and English/Arabic `get_views` calls.

Validation: 22 Odoo tests passed, including desktop/Arabic-mobile browser tests.
Follow-up XML regression: all five views passed source loading and `get_views`
in English and Arabic with `--dev=xml`; no Odoo restart or module upgrade needed.
Latest verification scan: 125 installed addons, 1,677 Python files, 42 definitions
across 19 addons, 329 executions; no scan warnings. Browser discovery results
were rolled back by Odoo's test transaction. No live discovery was pre-populated.
The original classification run's stored counters and UUID remain unchanged.

Files changed:

- `__init__.py`
- `__manifest__.py`
- `models/__init__.py`
- `models/definition.py`
- `models/discovery.py`
- `models/monitor.py`
- `services/__init__.py`
- `services/runtime.py`
- `services/static_discovery.py`
- `security/security.xml`
- `security/ir.model.access.csv`
- `views/monitor_views.xml`
- `static/description/icon.png`
- `static/src/monitor.js`
- `static/src/monitor.xml`
- `static/src/monitor.scss`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/__init__.py`
- `tests/test_monitor.py`
- `tests/test_ui.py`
- `docs/architecture.md`
- `changelog.d/current.md`

## Recent documentation commit

Commit: `6a1453f408aa22a8ecdcd265292b18988ca8446f`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `ab_queue_monitor/docs: record discovery dashboard commit and validation`

- Record discovery/dashboard implementation and validation evidence.

Files changed:

- `ab_queue_monitor/changelog.d/current.md`
- `ab_queue_monitor/changelog.d/2026-10-05-commit-review.md`

## Current changes before commit:

- Sort all five Job Definitions columns in either direction before pagination,
  retaining filters and showing the active direction.
- Separate runner lease detection from unverified execution progress. Show the
  last retained completion without presenting it as a heartbeat.
- Add a configurable age warning (default 30 minutes), global review count and
  review filter. Respect future ETA and recent enqueue times; do not declare
  old jobs dead or change their queue state.
- Stop failed/terminal durations from increasing without a reliable end time;
  display Unknown instead. Keep completed/cancelled durations fixed.
- Include older running, retrying, waiting and failed executions in definition
  status/filtering and display their counts beside the latest execution.
- Isolate discovery aliases by function, nested scope and assignment order;
  avoid guessing conflicting aliases after conditional branches.
- Refresh runtime data every 30 seconds while visible, with an opt-out, last
  update timestamp and a 90-second stale warning. Pause automatic requests
  during discovery/in-flight requests and clean up when navigating away.
- Translate new labels in both Arabic catalogs, including the existing Unknown
  term's new frontend reference, using an Odoo-exported POT.
- Add duration/ETA, mixed-execution, scope, permission, translation, browser and
  refresh-lifecycle regression checks. Document the monitoring limits.

Validation (2026-10-06): targeted upgrade on isolated database
`codex_queue_sort_20261006`, HTTP 5069/gevent 5072, workers/cron/queue runner
disabled. The 35 selected Odoo tests cover 32 backend cases and three browser
cases: 33 now pass and two optional classification cases are skipped because
that module and its executions are absent. The first browser run found missing
frontend translation metadata for Unknown; after merging its POT reference,
the targeted feedback test passed with zero failures/errors. Logs:
`/tmp/ab_queue_reliability_tests.log` and `/tmp/ab_queue_feedback_final.log`.
The Node refresh lifecycle checks, all exported strings in ar/ar_001,
`msgfmt --check-format`, Python/XML/JS parsing, SCSS compilation, source scanning
of four affected/relevant addons, and `git diff --check` passed.
The running website database was not upgraded and its service was not restarted.

Files changed:

- `ab_queue_monitor/changelog.d/current.md`
- `ab_queue_monitor/docs/architecture.md`
- `ab_queue_monitor/i18n/ar.po`
- `ab_queue_monitor/i18n/ar_001.po`
- `ab_queue_monitor/models/definition.py`
- `ab_queue_monitor/models/monitor.py`
- `ab_queue_monitor/services/runtime.py`
- `ab_queue_monitor/services/static_discovery.py`
- `ab_queue_monitor/static/src/monitor.js`
- `ab_queue_monitor/static/src/monitor.scss`
- `ab_queue_monitor/static/src/monitor.xml`
- `ab_queue_monitor/tests/check_monitor_refresh.cjs`
- `ab_queue_monitor/tests/test_monitor.py`
- `ab_queue_monitor/tests/test_ui.py`
- `ab_queue_monitor/views/monitor_views.xml`
