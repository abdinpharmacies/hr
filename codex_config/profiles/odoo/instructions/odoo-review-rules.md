# Odoo Review Rules

Apply the relevant checks in the main session when reviewing changes or checking
your implementation. These rules do not require delegation or four separate
reviews for every task. Follow the current user request and applicable repository
guidance; load only relevant skills/references. Keep private data confidential.

For a review-only request, inspect code and supplied evidence without editing,
changing databases, publishing, connecting to external databases, or restarting
services. An explicit implementation/validation request retains its authorized
scope; these review rules do not forbid that work. Report findings by severity
with file/line or symbol, impact and smallest correction. Distinguish confirmed
defects, missing evidence and proposed checks; never invent test results.

## Security

When authorization or data visibility is affected, check effective/implied groups,
explicit ACLs, rules on headers and lines, Python field groups, public methods
and controllers, scoped `sudo()`, branch/company isolation and security tests.
Trace realistic unauthorized direct ORM/RPC access, not just menu visibility.
Check intended manager/admin access before inherited lower roles. Include actor
and reproducible access path in findings. Use `odoo-security-review` as needed.

## Architecture

When module structure or integration changes, check ownership, manifest
depends/auto_install, registry relations, optional model availability, duplicate
responsibilities and integration boundaries. Keep `ab_hr` dependencies explicit,
groups in security XML/CSV and module installation out of Python. Constraints do
not replace read isolation. Preserve XML IDs and existing model names; no
unrelated renaming. Check existing `ab_*` ownership, especially product sync
versus SEO. Use module-development and SEO skills only when relevant.

## B-Connect / E-Plus

When external integration is affected, check parameterization, IN expansion,
branch/store predicates, header-line joins, decimal unit conversion and zero/null
handling, encrypted names, stable IDs, transaction boundaries and external writes.
Require an explicit consistency decision for `NOLOCK`. Check queue validation,
bounded retries, idempotency, audit and pushed transaction IDs. Review code and
evidence without executing external SQL merely to review it. State the affected
branch/data scenario. Use `bconnect-eplus` and relevant references.

## Final Validation

Before completing changes, check changed files, Odoo 19 APIs/views/assets,
imports, manifest dependency/load order, actual test counts and targeted
install/upgrade evidence. Review security regressions, both Arabic catalogs,
runtime language checks and production packaging. Confirm correct addons/DB
selection and alternate validation ports. Report passed checks and unverified
risks separately. Use validation, compatibility and translation skills as needed;
do not run a DB upgrade or restart a process solely to review existing evidence.
