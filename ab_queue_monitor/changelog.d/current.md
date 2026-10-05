# ab_queue_monitor

## Implementation record

Author: Mohamed Fawzy
Date: 2026-10-05
Commit: `f4a5294ff2f6a55dd44c51b683b6ff9617a09906`
Original subject: `feat(queue-monitor): add job discovery and execution dashboard`

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

## Current changes before commit:

- Record the module commit and link the current review validation in [the commit review](2026-10-05-commit-review.md).

Files changed:

- `ab_queue_monitor/changelog.d/current.md`
- `ab_queue_monitor/changelog.d/2026-10-05-commit-review.md`
