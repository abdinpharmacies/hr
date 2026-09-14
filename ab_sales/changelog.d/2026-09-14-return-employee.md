# Callcenter return employee — 2026-09-14

Recent relevant commit:
- Commit: `c6aeeec97a7c7121f8c7507488f3eef06d16f3f8`
- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-09-09 12:19:10 +0300
- Original commit subject: `ab_sales/edit after switching to json-2`
- Updated JSON-2 branch connections, health jobs, workflow documentation and
  Arabic translations.

Files changed in that commit:
- `BRANCH_API_WORKFLOW.md`
- `__manifest__.py`
- `changelog.d/2026-09-07-branch-api-client.md`
- `changelog.d/2026-09-09-json2-connections.md`
- `data/branch_connection_jobs.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/ab_sales_branch_rpc_config.py`
- `views/ab_sales_branch_rpc_config_views.xml`

Current changes before commit:

- Add an Administrator-only Return Employee selector to the standard return
  form; require a selection before submitting without a POS employee session.
- Send the active POS employee after checking session ownership, return-screen
  permissions and store access. Other users require an active employee session.
- Validate an active employee/cost center and stable code before creating an
  outbound submission log or request. Branch E-Plus IDs are validated remotely.
- Document the separate branch employee-validation extension and add both
  Arabic translations from a native Odoo POT export.
- Verify a targeted callcenter upgrade, actual submit argument forwarding with
  mocked RPC, field security, session restrictions and Arabic UI/error text.
- Preserve the existing native DB-serial and connectivity changes documented in
  their own changelog entries. This employee change is callcenter-worktree only.

Files changed for the return employee work:
- `models/ab_sales_branch_api_client.py`
- `views/ab_sales_return.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `BRANCH_API_WORKFLOW.md`
- `changelog.d/2026-09-14-return-employee.md`
