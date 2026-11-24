# Two-server QA follow-up

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

## c21a2076fb3142403b63ad3d6386a8bc97db1479

Author: Alhassan Hossny
Date: 2026-11-15
Original commit subject: ab_crm_sales_workspace/feat: unify contact inboxes and improve channel navigation and notifications

- Verify shared contact inbox and channel navigation behavior.

Files changed:
- tests/test_workspace.py

## Changes recorded during that development session:

This entry describes the QA follow-up; earlier uncommitted workspace implementation is preserved.

- Exercise Arabic runtime translations using the Arabic language codes actually activated in the synthetic database; Odoo's standard Arabic record uses ar_001.
- Verify received-message inbox ordering, private reads, shared agents and audited contact operations in the two-server QA matrix.
- Add no runtime source strings or translation changes in this follow-up.

Files changed:
- tests/test_workspace.py
- changelog.d/2026-11-23-two-server-qa.md
