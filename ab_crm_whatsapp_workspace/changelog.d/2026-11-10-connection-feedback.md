# Connection recovery and native feedback

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates`

## Changes included in implementation commit `fc6257ab`

- Version 19.0.1.6.0 routes WhatsApp template errors, unsupported layouts and incomplete-parameter notices through native Odoo notifications. Reuse the Sales Chatter feedback service and retain guarded template submission. Update browser expectations.

Files changed for this increment:
- `__manifest__.py`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/tests/drafts.test.js`
- `changelog.d/2026-11-10-connection-feedback.md`
