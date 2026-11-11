# Fix existing call-center return loading

## Recent relevant commit (return-header excerpt)

- Commit: `71c1fa4d9c1e3b9b11df6a70d1b12fc4eb49e9a3`
- Author: emadco88
- Date: 2026-10-08 01:33:29 +0300
- Original commit subject: ab_branch_api/ UPD compatible with callcenter19 ab_sales
- Added guarded call-center sale submission; also introduced a misplaced sale-default reset into existing return-header handling.

Files changed (relevant excerpt):
- `ab_branch_api/models/branch_api.py`

## Current changes before commit:

- Remove the misplaced sale-default reset from return-header reuse. It referenced undefined `header_model`, `allowed`, and `values`, causing existing return loading or submission to fail before return access and identity checks.
- Preserve return-header reuse, branch/invoice matching, call-center origin checks, and header/line write-access checks.
- No user-facing strings added or changed; Arabic translation catalogs require no changes.

Files changed:
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/changelog.d/2026-10-12-return-header-reuse.md`

Validation:
- Reproduced the original `NameError` by executing the actual method body with isolated model doubles.
- After the fix, verified repeated reuse, first creation and operation binding, missing source rejection, write-access rejection, and wrong-branch/wrong-invoice/non-call-center rejection.
- Python parsing and `git diff --check` passed. No database records or external stock/sales operations changed.
- Local call-center logs show connection 14 failing on `get_return_invoice` with HTTP 500. Its target is the remote branch server; that server's traceback was not available to confirm its exact exception.
- Deploy the Python fix and restart the affected branch Odoo workers. No schema changes or module upgrade are needed for this fix. No remote deployment or live restart performed.
