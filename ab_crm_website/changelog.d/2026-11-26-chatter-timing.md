# Sales Chatter timing

Current changes before commit:

- Use authorized target-scoped incremental queries, counts and lifecycle lookup instead of loading full target histories.
- Preserve independent targets and pagination across legacy aliases, including backdated arrivals and exact personal-read invalidations.
- Add target isolation and burst regressions; release version 19.0.1.18.0 with the matching Sales Chatter update.

Files changed:

- `README.md`
- `__manifest__.py`
- `changelog.d/2026-11-26-chatter-timing.md`
- `models/adapter.py`
- `models/targets.py`
- `tests/test_independent_chats.py`
