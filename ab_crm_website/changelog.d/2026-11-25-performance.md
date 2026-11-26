# Preserve independent website targets during bounded workspace refresh

Current changes before commit:

- Cache canonical stream, target, preference and authorization lookups within the current request only.
- Select website inbox activity through ORM aggregates, including legacy aliases; serialize only selected order/Support targets.
- Count target unread messages and initialize read preferences through bounded ORM queries instead of loading complete histories.
- Apply personal target read positions before v2 candidate pagination and return exact per-target unread totals.
- Invalidate authorized workspaces when target preferences change; add scoped indexes and independent-target regression coverage.
- Bump version to 19.0.1.17.0, preserve English/Arabic UI strings and retain all UUIDs and business records.

Files changed:

- `__manifest__.py`, `models/adapter.py`, `models/targets.py`
- `tests/test_independent_chats.py`, `RELEASE.md`
- `changelog.d/2026-11-25-performance.md`
