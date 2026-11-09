# Module update committed — 5d7325a2

- Commit: `5d7325a25699e6013b8a2f3f716553eae76187aa`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:04:35+02:00
- Original subject: ab_crm_messaging/feat: preserve historical message provenance and chronology

Preserve historical-import provenance and provider chronology, reject unsupported incoming identities, and permit inactive scoped service users only for disabled accounts.

Commit preparation checks: changed Python, XML, JavaScript and JSON syntax; SCSS compilation; all six Arabic catalog format checks; addon manifest paths and ownership metadata; and `git diff --check` passed. Earlier Odoo/gateway suite results remain recorded in the existing validation reports. Their temporary logs and test environment were unavailable in this session; those suites were not rerun for this commit. No live database upgrade or service restart was performed.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/messaging.py`
