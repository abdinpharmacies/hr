# Recent Changes

## a303784 - Mohamed Fawzy - 2026-08-06 - ab_supplier_claim_workflow/chore:add all imports in model init

- Ensured all workflow model files are imported by the module initializer.

Files changed:
- `models/__init__.py`

## Current changes before commit:

- Added department-level `Deferred` decisions for supplier claim workflow stages.
- Added expected completion date, deferral reason, and overdue-day tracking for each department.
- Added a defer dialog to collect expected completion date and deferral reason when they are missing.
- Restyled the defer dialog with the module's clean modern dialog layout.
- Added actual overdue days to deferred stage-history notes.
- Made deferred timeline notes recalculate actual overdue days dynamically from the expected completion date.
- Added a dedicated timeline line for delay days after the expected deferral date.
- Changed the deferred timeline line to show remaining days before the expected deferral date and overdue days after it passes.
- Added state-aware timeline colors for deferred remaining and overdue day badges.
- Restricted actual overdue-day visibility to Secretarial and Admin users.
- Renamed delay/rejection wording to rejection-only wording in the workflow form and validation messages.
- Marked deferred workflow popup and history messages as Python translations for Arabic runtime rendering.
- Added a `Defer` workflow button for department groups only.
- Fixed the Arabic translation reference for the `Defer` workflow button.
- Blocked finishing a deferred department request until it is accepted or rejected.
- Reset department overdue and escalation counting to start after the deferred expected completion date.
- Added claim-created chatter notifications for supplier claim module users, excluding admin/system managers.
- Blocked registering supplier claims with a zero cheque amount so notifications do not show `0.00`.
- Added a department-turn notification hook for Telegram extensions.
- Added focused workflow test coverage for department deferral behavior.
- Added Arabic translations for new deferred workflow strings.
- Granted reviewers read-only access to supplier claim blocking issues so claims open without access errors.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/ab_supplier_claim_cycle.py`
- `models/ab_supplier_claim_defer_wizard.py`
- `models/ab_supplier_stage_history.py`
- `security/ir.model.access.csv`
- `static/src/scss/supplier_claim_cycle.scss`
- `tests/test_supplier_claim_workflow.py`
- `views/ab_supplier_claim_cycle.xml`
- `views/ab_supplier_claim_defer_wizard.xml`
