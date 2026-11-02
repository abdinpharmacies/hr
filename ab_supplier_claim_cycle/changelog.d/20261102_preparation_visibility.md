Current changes before commit:

- Move Secretarial Preparation into Review Details and remove its separate tab.
- Show preparation content only when the current user can prepare
  payment: an authorized secretary or administrator, on an active claim at the
  preparation stage with pending or returned preparation.
- Reuse the existing permission field and retain server-side action checks.
- Retain Review Details for secretaries, filter preparation content by role on
  the server, and include the secretary role in the view cache key.

Files changed:
- views/parallel_workflow.xml
- models/ab_supplier_claim_cycle.py
- tests/test_claim_cycle.py
- changelog.d/20261102_preparation_visibility.md
