# Website transaction conflict recovery

## b2184730c5d9f9cbcad425bfe427dc40fcce1eb1

Author: Alhassan Hossny
Date: 2026-11-15
Original commit subject: crm_messaging_gateway/feat: add website exchange, read receipts and animation handling

- Add website-specific exchange routing to the Odoo client.

Files changed:
- app/odoo.py

## Current changes before commit:

This entry describes the QA follow-up; earlier uncommitted gateway implementation is preserved.

- Retry website-account HTTP 409 transaction conflicts at most four times, preserving the exact payload, correlation, receipt, token and destination.
- Keep exhausted website conflicts transient so durable queue recovery does not treat them as permanent validation failures.
- Preserve the existing retry behavior of other providers and the existing credential-fetch retry policy.
- Add focused tests for website JSON/controller transports, bounded retries, identical replay and non-replayed authentication/validation/server failures.

Files changed:
- app/odoo.py
- tests/test_odoo_conflicts.py
- changelog.d/2026-11-23-two-server-qa.md
