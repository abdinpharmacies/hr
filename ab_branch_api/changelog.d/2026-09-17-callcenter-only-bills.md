# ab_branch_api: call-center-only bills

## Recent commit

Commit: `4ac5a5204558fa866ed7c7cca08395695e8046cc`

Author: Hossam Elsheikh

Date: 2026-09-17T10:04:25+03:00

Original commit subject: ab_branch_api: add ownership-scoped call-center sale status refresh

- Add ownership-scoped refresh for verified call-center submissions.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-callcenter-order-status.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/callcenter_services.py`

## Current changes before commit:

- Add immutable, indexed call-center origin markers to sale/return headers through API-owned inheritance and read-only forms; leave existing records and copies unmarked.
- Restrict bill searches, totals, snapshots, details, notes and printing to marked records in the authorized branch, with drafts included when no status is selected.
- Require a marked original sale for API returns; exclude branch-created returns and preserve origin on submission retries.
- Advertise the callcenter_only capability, reject old bill snapshots, and support empty result pages.
- Preserve verified submission status refresh without enrolling browsed bills; update Arabic translations and provider-first rollout instructions.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-callcenter-only-bills.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/callcenter_origin.py`
- `ab_branch_api/models/callcenter_services.py`
- `ab_branch_api/views/api_views.xml`

Validation: targeted upgrades on isolated database copies; real ORM origin/access/filter/pagination and print checks; mocked transport and external SQL; status-refresh and retry regressions; Arabic runtime checks; PO format, Python/XML/JS syntax, and diff checks. Test scripts and results are outside the addons at `/tmp/callcenter_origin_validation`. No production database upgrade or external database writes.
