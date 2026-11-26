# Sales Chatter timing

Current changes before commit:

- Refresh the active conversation independently, coalesce resource requests, refresh contacts on changes and retain five-second recovery polling.
- Add authorized capped incremental updates, refresh only visible cached messages, preserve ingestion cursors and batch page previews without changing incoming inbox ordering.
- Send capped canonical conversation IDs and categories on private partner channels; scope read invalidations to the employee and refresh authorized directory changes.
- Add opaque opt-in timing events, regression coverage, scalable API fixtures and version 19.0.1.44.0.

Files changed:

- `README.md`
- `RELEASE.md`
- `__manifest__.py`
- `changelog.d/2026-11-26-chatter-timing.md`
- `models/invalidation.py`
- `models/timing.py`
- `models/workspace.py`
- `static/src/chat_controls.js`
- `static/src/session_service.js`
- `static/src/timing.js`
- `static/src/workspace.js`
- `static/tests/composer.test.js`
- `static/tests/notifications.test.js`
- `static/tests/timing.test.js`
- `tests/test_branch_browser.py`
- `tests/test_workspace.py`
