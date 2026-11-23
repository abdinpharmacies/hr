# Website chat source, identity and terminal lifecycle

Recent relevant commit:

- Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: `ab_crm_website/feat: group orders into receive-only customer conversations`
- Change: Group website orders into customer conversations while retaining order references and scoped evidence.
- Files changed: `__manifest__.py`, `README.md`, `models/adapter.py`, `security/ir.model.access.csv`, `security/security.xml`, `views/views.xml`, `i18n/ar.po`, `i18n/ar_001.po`, `tests/test_contact_groups.py`, `tests/test_adapter.py`, `tests/test_pos.py`, `tests/contact_group_concurrency.py`, `changelog.d/2026-11-16-customer-conversations.md`, `changelog.d/2026-11-16-link-candidate-locks.md`, `changelog.d/2026-11-16-receive-only.md`.

Current changes before commit:

- Validate optional customer phone metadata without using it to merge account identities; show verified account names and phones, including explicit empty phone and legacy omission.
- Show source icons only in the conversation header channel, using stored relations and selected reply targets: the existing floating-chat bot and the supplied image for order conversations. Keep message bubbles and reply previews free of repeated source icons.
- Accept order-only `order_dispatched` events, persist terminal closure per order, and append one translated closure notice while preserving the assigned agent and other destinations.
- Deduplicate guest leave notices, retain history, and recheck terminal destinations for direct replies, selected uploads, queued sends and final send authorization.
- Show the closure reason on unavailable reply actions and translate persisted notices at display time; keep endpoint-configuration errors distinct.
- Reject customer envelopes whose UUID conflicts with an already bound order owner before accepting display metadata.
- Maintain both Arabic catalogs and regression coverage for per-order isolation, queue revalidation, assignment preservation and customer metadata.
- Preserve the pre-existing uncommitted native chat, private media, reply, saved-reply and reliability work documented in earlier change records.

Files changed:

- `__manifest__.py`
- `README.md`
- `protocol.py`
- `models/adapter.py`
- `controllers/adapter.py`
- `static/src/order.xml`
- `static/src/reply.js`
- `static/src/order.scss`
- `static/src/img/callcenter_support.png`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_contact_groups.py`
- `changelog.d/2026-11-22-chat-identity-dispatch.md`
