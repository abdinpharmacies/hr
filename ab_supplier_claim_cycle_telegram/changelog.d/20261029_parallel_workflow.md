# Parallel claim notification routing

Current changes before commit:

- Notify actionable departments in parallel stages and Secretarial preparation.
- Require recipient company membership and claim read access.
- Preserve bank-return action arguments and notify on preparation completion.
- Adapt mocked integration tests to the new workflow.

Files changed: `__manifest__.py`, `models/supplier_claim_cycle.py`,
`tests/test_telegram_notifications.py`.
