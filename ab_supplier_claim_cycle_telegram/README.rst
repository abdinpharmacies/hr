Supplier Claim Cycle Telegram Notifications
===========================================

This addon extends validated claim actions and stores delivery jobs in the same
transaction. It adds no fields or database models. Claim actions never call Telegram.

Routing
-------

* Inventory, Purchasing, Supplier Accounts and Bank Accounts receive their stage.
* Secretarial receives rejected claims and claims ready to close.
* The creator receives final closure.
* Cash submissions go directly to Supplier Accounts.
* Resubmissions notify the resumed department; deferrals enqueue nothing.

Recipients are active internal group users matched through
``ab_hr_employee.user_id``. Each employee's cost center supplies its latest active
``ab_partner_bot`` account. Employees without a connected account are skipped.
Chat IDs are deduplicated per transition. One job per chat preserves independent
retries. Jobs capture the claim details and stage when the transition occurs.
Messages contain the claim ID, supplier, amount, stage, rejection reason when
applicable, and the Odoo link. Attachments are not sent.

Configuration
-------------

The existing ``telegram.notifications.enabled`` setting controls supplier
notifications. If it is absent, notifications default to enabled without
creating a system parameter.
Setting it to ``False`` prevents new jobs and skips pending deliveries.

Supplier delivery reads the existing shared ``telegram.bot.token`` under
Settings / Technical / Parameters / System Parameters. It does not create any
token or enable/disable parameters. There is no fallback to a different token
parameter; other modules retain their existing token lookup behavior.
Do not put the token in repository files. Recipients must start the shared bot
before it can message them, even if their Chat IDs are already linked.

When notifications are enabled but this token is missing or blank, transitions
still enqueue delivery jobs for connected recipients. Those jobs retry with a
configuration error until the token is supplied or notifications are disabled.
The token is read when the job runs and is never stored in job arguments.

Load ``web,queue_job`` in ``server_wide_modules`` and configure::

    [queue_job]
    channels = root:2,root.supplier_claim_cycle_telegram:1

The private delivery method calls ``ab_telegram_bot.send_message()``. API failures
and communication exceptions raise ``RetryableJobError``. Retries are unlimited,
with delays of 60 seconds initially, 300 seconds from attempt 3, 900 seconds from
attempt 5 and 3600 seconds from attempt 10. Monitor failed or repeatedly retrying
jobs in Job Queue. A lost Telegram response can cause a delivery retry after
Telegram has already accepted a message.

Verification
------------

Run Odoo with ``--test-enable --test-tags /ab_supplier_claim_cycle_telegram``.
Tests mock Telegram delivery and roll back fixtures. Coverage includes both
routes, each department's rejection and resubmission, deferral, closure, access
checks, recipient deduplication, missing connections, transaction rollback,
message snapshots, retry behavior, the configuration switch and multi-record
submission. Where installed, the replica cost-center guard is mocked only for
disposable test fixtures.
