# WhatsApp reception, contacts and templates

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:05:37+02:00
- Original subject: ab_crm_sales_workspace/docs: record grouped chatter and menu fixes

## Changes included in implementation commit `77209fcb`

- Use effective human contact names and preserve the active conversation after editing.
- Add reviewed contact linking/creation, verified-phone agent permissions, channel styling and circular send control.
- Render explicit shared-contact save actions and extend reaction visibility/alert hooks.

Validation and rollout evidence: `docs/whatsapp-reception-rollout.md`. Runtime rollout and live provider acceptance remain pending the user-managed maintenance window.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/alerts.py`
- `models/customer_streams.py`
- `models/directory.py`
- `models/workspace.py`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/templates.js`
- `static/src/workspace.js`
- `static/src/workspace.scss`
- `static/src/workspace.xml`
