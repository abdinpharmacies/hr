# WhatsApp reception, contacts and templates

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:05:37+02:00
- Original subject: ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates

## Changes included in implementation commit `fc6257ab`

- Receive WhatsApp profiles, private media, contact cards and timestamp-ordered reactions with canonical history.
- Synchronize account-owned templates atomically, show all languages and reject unsupported layouts.
- Preserve original sender-branch dispatch authorization and add reception/link/template/browser regressions.

Validation and rollout evidence: `docs/whatsapp-reception-rollout.md`. Runtime rollout and live provider acceptance remain pending the user-managed maintenance window.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-09-dispatch-sender-branch.md`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
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
