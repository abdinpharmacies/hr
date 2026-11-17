# Website contact candidate preview without account locks

Current changes before commit:

- Keep staff/session/branch/company authorization for Website saved-contact candidates, and remove write locks from the read-only candidate lookup.
- Verify candidate lookup remains available while the messaging account is busy and unauthorized users remain denied.

Files changed:

- `__manifest__.py`
- `models/adapter.py`
- `tests/test_contact_groups.py`
- `changelog.d/2026-11-16-link-candidate-locks.md`
