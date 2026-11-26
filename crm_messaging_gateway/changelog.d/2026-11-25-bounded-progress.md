# Drain eligible work in fair bounded scheduling cycles

Current changes before commit:

- Report durable progress, including deferrals, from queue operations; continue immediately while eligible work remains.
- Rotate operation/account scheduling within 25 operations or 250 ms between operations, retaining existing leases, provider timeouts, retries and uncertain-send review.
- Rotate receipt/report evidence through bounded windows so one failed row does not starve the next row.
- Bound website fetch intake to 25 events per scheduled fetch, rotate protocol versions/accounts, and add explicit validated account selection.
- Prepare separate mutually exclusive pilot/production website worker templates without installing or enabling them.
- Retain current PostgreSQL/Odoo coupling, idle polling and failure backoff; do not claim production capacity or PostgreSQL independence.

Files changed:

- `app/worker.py`, `app/website.py`, `tests/test_worker_scheduling.py`
- `deploy/crm-messaging-website-pilot@.service`, `deploy/crm-messaging-website-production@.service`
- `README.md`, `changelog.d/2026-11-25-bounded-progress.md`
