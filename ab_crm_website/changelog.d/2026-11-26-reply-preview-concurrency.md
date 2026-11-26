# Avoid website reply-preview locks during workspace polling

Current changes before commit:

- Bump the module version to 19.0.1.18.1.
- Validate per-message reply destinations without row locks while serializing workspace detail and updates, avoiding serialization failures against concurrent website intake updates.
- Keep order/session locks enabled by default for reply submissions, uploads, approvals and delivery; retain authorization, company/branch scope and closure checks.
- Add focused regressions covering order and Support polling under simulated serialization conflicts, required submission locks and closed-target rejection.
- Preserve the existing timing changes recorded separately in `2026-11-26-chatter-timing.md`; introduce no new UI strings or translation changes.

Files changed:

- `README.md`
- `__manifest__.py`
- `models/adapter.py`
- `models/media.py`
- `tests/__init__.py`
- `tests/test_reply_concurrency.py`
- `changelog.d/2026-11-26-reply-preview-concurrency.md`
