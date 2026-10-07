# ab_branch_api: protected callcenter sale submission

## Recent commit

Commit: `16fb3b5a0aac5304178b38de27e289414a6eb1c0`

Author: Alhassan Hossny

Date: 2026-10-07T15:06:16+03:00

Original commit subject: ab_branch_api/Update: post callcenter sales through branch workflow

- Posted callcenter sales through the normal branch workflow with stable request tokens.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-10-07-automatic-callcenter-sale-posting.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/branch_api.py`

## Current changes before commit:

- Expose the sales submission guard capability and a versioned outcome with token, revision, bill IDs, status and diagnostic.
- Keep Unknown requests immutable and allow corrected revisions only after confirmed rejection, on the same bill and token.
- Revalidate failed corrections atomically; preserve normal store, product, UoM, promotion and contract checks.
- Use the native sale guard with a dedicated SQL session and retain the connector factory after API preparation disables pooled reconnect.
- Recover committed Unknown bills through read-only branch-scoped evidence; observation never creates a sale or consumes stock.
- Allow active internal users, including Settings/access administrators and an active superuser, to connect with their own native API keys; retain activity, internal-user, ownership, scope, expiry, business-permission and replica/store checks.
- Keep return posting/recovery unchanged; add Arabic translations, administrator revision display, rollout documentation and version 19.0.5.5.1.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-10-08-protected-branch-sale-submission.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/callcenter_services.py`
- `ab_branch_api/models/credentials.py`
- `ab_branch_api/models/guarded_sales.py`
- `ab_branch_api/models/reconciliation.py`
- `ab_branch_api/models/routing.py`
- `ab_branch_api/views/api_views.xml`

Validation:

- Targeted isolated module installs/upgrades, Python/XML/JS syntax and diff checks.
- Actual ORM guard, revision, rejected correction, concurrency, branch identity and pricing tests with fake external SQL.
- Two isolated Odoo registries over the actual JSON-2 client: lost HTTP/external commit acknowledgements, rejection/correction and original-payload retries.
- Real OWL browser mount with unchanged promotion, contract and employee patches; UI locks, delayed pricing callbacks, focus refresh and listener cleanup.
- Arabic PO format checks and runtime ar_001 status/view translations.
- Actual native API keys and public connection-status checks for ordinary internal users, Settings/access administrators and the conditional active-superuser case; temporary isolated fixtures rolled back.
- Reject inactive, portal/public, missing/invalid, expired, wrong-scope and wrong-owner credentials; enforce replica/store isolation and existing business ACLs; verify the new message in ar_001.
- No production database changes, real E-Plus writes, production restarts or commits.
