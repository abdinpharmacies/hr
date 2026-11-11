# Module update commit record

- Commit: `fc6257abbe9867771848594fa4aa50d99d981f1e`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:50:38+02:00`
- Original subject: `ab_crm_whatsapp_workspace/feat: extend reception and reconcile historical receipts`

## Changes

- Extend WhatsApp reception, media and template validation, preserve dispatch branch scope, and reconcile uniquely verified historical delivery receipts without sending messages.
- Detailed feature entries in this directory describe the constituent updates.

## Validation

Implementation and runtime evidence is recorded in [the retirement report](../../docs/messaging-legacy-retirement.md) and the feature-specific rollout reports in `docs/`. Commit preparation checked changed Python syntax, XML parsing, JavaScript syntax, Arabic catalog formats and whitespace. No additional runtime or database changes were made while preparing commits.

Files changed:

- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/account.py`
- `models/gateway.py`
- `models/history.py`
- `models/media.py`
- `models/service.py`
- `models/workspace.py`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/tests/drafts.test.js`
- `tests/test_bridge.py`
- `views/account.xml`
