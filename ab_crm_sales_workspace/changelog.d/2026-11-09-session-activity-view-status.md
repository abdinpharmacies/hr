# Session activity contention and informational banners — 19.0.1.14.1

Current changes before commit:
- Give the Telegram setup and branch-location informational banners `role="status"`, preserving their text, translations, styling, XML IDs and architecture whitespace.
- Lock stale session rows with Odoo's nonblocking `try_lock_for_update(allow_referencing=True)` before updating activity. Skip only the optional activity write when busy, invalidate/re-read the timestamp after locking, and retain native transaction retries.
- Preserve staff/user/company/employee authorization, expiry, revocation and the one-minute activity interval.
- Add regression coverage for fresh/stale activity, timestamp re-reading, expiry and company isolation, plus a dedicated independent-transaction runner covering busy rows, rollback recovery and committed-update retries.

Files changed:
- `__manifest__.py`
- `models/session.py`
- `views/telegram_setup.xml`
- `views/branch_location.xml`
- `tests/test_workspace.py`
- `tests/session_concurrency.py`
- `changelog.d/2026-11-09-session-activity-view-status.md`
