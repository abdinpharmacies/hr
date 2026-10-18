## e28bbc1da77e78c8710e4deff47be9b0accb2b1e — Hossam Elsheikh — 2026-10-15T11:18:45+03:00

Original commit subject: ab_branch_api/- Removed backend SQL, connections, and recovery implementation from ab_branch_api. - Preserved all 20 endpoint signatures. - Updated translations, documentation, and changelogs.

User-facing changes:
- Delegate backend operations to the sales module while preserving API endpoints.

Files changed:
- ab_branch_api/BRANCH_API_BACKEND_INDEPENDENCE_PLAN.md
- ab_branch_api/README.md
- ab_branch_api/changelog.d/2026-10-15-backend-independence.md
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/callcenter_services.py
- ab_branch_api/models/customer_sync.py
- ab_branch_api/models/guarded_sales.py
- ab_branch_api/models/reconciliation.py
- ab_branch_api/models/routing.py
- ab_branch_api/models/sale_validation.py
- ab_branch_api/models/sales_workflow.py

## Current changes before commit:

- Give Branch API an explicit plain-text module description so Odoo does not parse Markdown README tables as reStructuredText.
- Remove the line-block warnings and undefined substitution errors during module description rendering; preserve the detailed README.
- Translate the description in both Arabic catalogs.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/changelog.d/2026-10-18-description-rendering.md

Validation:
- Reproduced the original console messages from this worktree's README with docutils before the fix.
- Completed the targeted ab_branch_api upgrade on the configured database using alternate ports and disabled cron workers, without stopping the user's server.
- Exported the module POT using Odoo 19 and verified the module-description XML ID at runtime.
- Both Arabic catalogs pass msgfmt --check-format.
- Three runtime checks pass: English description rendering, Arabic description rendering, and differing English/Arabic menu labels.
- Description rendering produces no docutils diagnostics in either language.
- Existing unrelated missing store_id values on ab_sales_return_header still produce a schema error during upgrade; no business data was repaired by this change.
