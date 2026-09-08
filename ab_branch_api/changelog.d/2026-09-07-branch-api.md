# Branch API

No previous commits: this is a new module.

Current changes before commit:

Author: hossam elsheikh
Date: 2026-09-07

- Add a version 1 branch provider for product queries, live stock batches, sale submission, return loading and previews, return posting, and operation status.
- Resolve cross-database records using E-Plus identifiers, codes, or shared XML IDs; resolve employee references through cost-center codes and product units by category and factor.
- Restrict each API caller to explicit active user/store bindings, with separate posting and cost permissions. API User membership (or Settings access) is required; bindings remain mandatory for administrators.
- Reuse existing branch sales and return methods, including contract/promotion extensions and E-Plus replication. API return operators use the supplied employee reference when available.
- Reserve posting requests before E-Plus writes. Completed requests replay their result; uncertain outcomes block automatic replay. Retain partial transaction identifiers for reconciliation and prevent concurrent API returns for the same invoice.
- Provide English source labels and Arabic translations for ar and ar_001.

Validation:
- Targeted installation and upgrades passed on branch development database abdin_pos using isolated ports, zero cron threads, and stop-after-init.
- Mocked connector tests passed: branch access and public-user denial; branch-filtered stock; cost permissions; XML-RPC serialization; bounded stock requests; completed-request replay; mismatched payload rejection; uncertain-outcome retry rejection.
- Actual provider posting tests passed with mocked business writes: create branch sale/return records, delegate posting once, replay completed requests, serialize results, and report operation status.
- Return selection tests passed: unit conversion, unknown invoice line, wrong product, negative/non-finite quantity, duplicate source lines.
- Odoo 19 POT export and msgfmt --check-format passed for both translations; the action name differs at runtime between en_US and ar_001.
- Python/XML parsing and manifest author/developer checks passed. No E-Plus business writes were executed by validation.

Deployment notes:
- Configure Sales / Configuration / Branch API / Access for the integration user and its allowed store. Posting and cost visibility are opt-in.
- Existing business ACLs still apply to the integration user. Use shared XML IDs for references without an E-Plus serial/code, such as promotion programs; numeric Odoo IDs are never interpreted as cross-database identities.
- An operation left processing or needing reconciliation must be investigated against E-Plus before any new submission. This version intentionally has no automatic reset/retry for uncertain writes.
- The callcenter consumer is implemented and validated in its separate workspace; enable the integration with explicit branch access and callcenter RPC settings.
- Return posting checks source branch, finalized invoice status, and return period before reserving an external write. Missing E-Plus server configuration is rejected.

Files changed:
- ab_branch_api/__init__.py
- ab_branch_api/__manifest__.py
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/security/security_groups.xml
- ab_branch_api/security/ir.model.access.csv
- ab_branch_api/views/api_views.xml
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/changelog.d/2026-09-07-branch-api.md
