# ab_branch_api: restore automatic branch-owned sale posting

## Recent commit

Commit: `176a039b07cab2c300df60ba5a0c684a337ec4cd`

Author: Hossam Elsheikh

Date: 2026-09-17

Original commit subject: ab_branch_api/No additional access rules are needed. This was a regression in my last commit

- Preserved normal read-only access for posted bills during recovery.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-recovery-readonly-access.md`
- `ab_branch_api/models/reconciliation.py`

## Current changes before commit:

- Create callcenter-origin sales as PrePending and automatically run the normal branch `action_submit()` workflow.
- Require successful automatic posting to return Pending/Saved with a positive E-Plus serial; never assign Pending directly.
- Reject the obsolete callcenter transport choice and keep posting policy inside the branch.
- Allow callcenter delivery sales without a selected branch courier by using the already validated invoice salesperson for the E-Plus delivery record; explicit couriers still take precedence.
- Preserve API authentication, branch isolation, request-token idempotency, recovery, and completed-result replay.
- Remove callcenter-facing delivery-employee validation and its obsolete translations.
- Document the paired rollout and bump the module version to 19.0.5.4.2.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-10-07-automatic-callcenter-sale-posting.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/branch_api.py`

Validation:

- Python AST parsing, diff checks, warning-free POT export, and both Arabic PO format checks pass.
- The targeted branch upgrade completed at 19.0.5.4.2; no invalid Pending/serial-zero branch invoice remains.
- Rollback-only ORM tests confirm delivery fallback, explicit-courier precedence, normal `action_submit()` dispatch, Pending with a positive serial, and rejection of the obsolete false transport choice.
- Live read-only capability checks confirm posting permission and the token-scoped status API. No E-Plus write was performed by automated validation.
