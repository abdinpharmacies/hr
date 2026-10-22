# Faster Telegram verification responses

## Recent relevant commit

Commit: `855b7dd`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `ab_ecommerce_storefront/feat: add verified email and Telegram account recovery`

User-facing changes:

- Add verified phone ownership through the existing Telegram bot before storefront account creation and recovery.
- Queue authenticated webhook updates and Telegram delivery through the storefront authentication service.

Files changed:

- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/data/auth_queue.xml`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/tests/test_authentication.py`

Validation:

- Four focused Odoo tests pass on `ab_auth_task26_test` using isolated ports `5069` and `5072`, covering authenticated webhook wake-up, duplicate update IDs, Odoo 19 cron triggers, and repeated Telegram starts.
- Python compilation, `git diff --check`, and both Arabic PO format checks pass. Pyflakes is not installed in the project environment.

## Current changes before commit:

- Wake the durable authentication delivery cron immediately after accepting a new Telegram webhook update instead of waiting for its next minute interval.
- Keep duplicate Telegram update IDs idempotent without creating redundant immediate cron triggers.
- Re-send the contact-sharing keyboard when the same Telegram account repeats the active deep-link start command, and confirm already verified requests without showing an expired-request error.
- Cover immediate queue wake-up deduplication and repeated-start contact-button behavior.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-22-telegram-queue-latency.md`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/docs/authentication.md`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/tests/test_authentication.py`
