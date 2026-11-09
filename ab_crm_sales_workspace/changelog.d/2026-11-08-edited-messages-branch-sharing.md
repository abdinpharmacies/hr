# Edited messages and branch sharing — 19.0.1.14.0

Current changes before commit:
- Always share a native location from the branch picker. Replace the content selector with an optional, initially unchecked Send branch details checkbox; keep the preview and Send button.
- Queue location and optional details atomically with deterministic, immutable retry identities.
- Show current incoming message revisions, attachment revisions, quotes and an Edited label. Refresh edits in already loaded older history while preserving drafts and scroll/navigation state.
- Freeze delivery-location coordinates when selected for an order; later Telegram location edits update the conversation without silently moving an order's destination. Preserve original evidence for older selections.
- Retain company/session/conversation checks, order routing restrictions and both Arabic catalogs. The existing account sending switch is configured on separately as authorized.

Files changed:
- `__manifest__.py`
- `models/branch_location.py`
- `models/orders.py`
- `models/workspace.py`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/composer.test.js`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-08-edited-messages-branch-sharing.md`
