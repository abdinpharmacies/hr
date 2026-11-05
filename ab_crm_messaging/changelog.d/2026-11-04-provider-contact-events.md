# Provider contact-event extension

Current changes before commit:

- Allow optional contact metadata in the fingerprinted incoming event envelope.
- Provide a provider-specific hook before committing the deduplication ledger; unsupported contact events fail closed.
- Preserve durable delivery leases, staff approval, receipts and uncertain-send review.

Files changed:

- `__manifest__.py`
- `models/messaging.py`
- `i18n/ar.po`, `i18n/ar_001.po`
- `changelog.d/2026-11-04-provider-contact-events.md`
