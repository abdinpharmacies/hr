# Sales Chatter timing

Current changes before commit:

- Expose bounded 100–2000 ms idle configuration with 250 ms defaults and legacy rollback values while retaining the existing fair bounded scheduler.
- Add opt-in hashed reception/queue/provider timing events and bounded configuration regression tests.
- Document separate account-selected production and pilot website commands; preserve provider timeout, leases, receipt and uncertain-outcome behavior.

Files changed:

- `README.md`
- `app/config.py`
- `app/main.py`
- `app/receiver.py`
- `app/timing.py`
- `app/website.py`
- `app/worker.py`
- `changelog.d/2026-11-26-chatter-timing.md`
- `tests/test_worker_scheduling.py`
