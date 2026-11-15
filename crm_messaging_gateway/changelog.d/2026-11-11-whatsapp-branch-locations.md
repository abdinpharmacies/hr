# Native WhatsApp branch locations

## Committed baseline

- Commit: `c37c7bf213785126738c3d3bf5880c7cf2640721`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:34+02:00`
- Original subject: `crm_messaging_gateway/docs: record reception recovery and reconciliation controls`

## Current changes before commit:

- Send validated branch locations through the WhatsApp location payload, retaining the account location gate, expiry checks and uncertain-delivery handling.
- Validation and rollout: [notification and branch location update](../../docs/simple-notifications-whatsapp-locations.md).

Files changed:

- `README.md`
- `app/__init__.py`
- `app/providers.py`
- `tests/test_branch_locations.py`
