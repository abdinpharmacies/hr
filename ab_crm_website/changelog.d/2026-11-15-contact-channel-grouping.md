# Website contact grouping and reviewed group links

Current changes before commit:

- Use shared contact grouping and the saved contact's name after reviewed linking; group only unlinked orders by submitted phone.
- Keep Website order references visible when navigating from every linked provider.
- Separate authorized contact navigation from Website-only invoice timeline membership.
- Supply all displayed orders to the shared reviewed-link operation, serialize intake against group confirmation and provide a bounded admin-only ORM grouping-key rollout.
- Cover grouped linking, pagination, stale/concurrent arrivals, rollback, access denial, conflicts, future providers and English/Arabic browser behavior; preserve invoice evidence, POS handoffs and reply destinations.

Files changed:

- `models/adapter.py`
- `tests/__init__.py`
- `tests/test_contact_groups.py`
- `tests/contact_group_concurrency.py`
- `tests/test_pos.py`
- `__manifest__.py`
- `changelog.d/2026-11-15-contact-channel-grouping.md`
