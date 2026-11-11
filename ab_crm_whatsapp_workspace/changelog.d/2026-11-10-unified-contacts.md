# Unified contacts and open reception

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates`

## Changes included in implementation commit `fc6257ab`

- Preserve opaque inbound identifiers in canonical history while retaining strict outgoing destination eligibility.
- Test unknown and international senders, multiple numbers, shared/archived numbers, queued destinations and canonical consolidation.
- Verify phone security, explicit Telegram association, runtime Arabic translations and LTR/RTL channel choosers.
- Retain the existing dispatch actor fix, media/reaction improvements and approved-template ownership controls.

Validation and rollout: `docs/unified-contacts-rollout.md`. Live rollout completed during the user-managed maintenance window; verification and remaining unmatched historical status evidence are recorded in the rollout document.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-09-dispatch-sender-branch.md`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `changelog.d/2026-11-10-unified-contacts.md`
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
