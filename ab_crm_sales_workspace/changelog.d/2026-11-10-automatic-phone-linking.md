# Automatic same-phone channel association

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.19.0 adds automatic association of unlinked Telegram/WhatsApp conversations with a unique active saved customer whose normalized phone matches verified channel evidence.
- Reconcile during authorized inbox/detail refresh and notification polling. Existing conversations are covered without a migration or cron. Do not create customers, rewrite catalog records or change existing owners automatically.
- Exact verified matches no longer require a review reason. The contact picker submits the fingerprint automatically; retain explicit review for unverified numbers, inactive identities and conflicting ownership.
- Preserve branch/company scope, caller permissions, branch locking, fingerprint rechecks, message IDs, order snapshots and queued destinations. Record automatic associations with employee, actor, time and phone evidence.
- Preserve all previous phone display, alert, reception and dispatch work. Existing English/Arabic strings and translations are unchanged.
- Add ordinary-user security, archived/shared-number, cross-channel grouping, no-prompt browser and real transaction-contention regressions.

Verification and intake diagnosis: `docs/automatic-phone-linking.md`.

Files changed for this increment:
- `__manifest__.py`
- `changelog.d/2026-11-10-automatic-phone-linking.md`
- `models/alerts.py`
- `models/customer_streams.py`
- `static/src/contacts.js`
- `static/tests/contact_phones.test.js`
- `tests/auto_link_concurrency.py`
- `tests/test_workspace.py`
