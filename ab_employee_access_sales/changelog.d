Current changes before commit:

- Make Synchronize Employee Sales Access create missing access profiles only; skip every existing profile, including roleless or manually disabled profiles.
- Preserve all existing login flags, roles, PINs, permissions and allowed stores. Remove automatic disabling, reenabling and session revocation.
- Create profiles only for active, working employees with a usable active job-to-role mapping; explicitly set employee, cost center, role and department store.
- New profiles without a department store receive their role with empty allowed stores and login disabled. Existing profiles are never changed when department/job data changes later.
- Retain PIN validation/generation, 500-employee batches, savepoint recovery and unique-profile enforcement. Preserve result/log counter keys; disabled, reenabled and revoked remain zero.

Files changed:

- ab_employee_access_sales/changelog.d
- ab_employee_access_sales/models/ab_employee_access.py

Validation:

- Targeted upgrade passed in isolated codex_employee_sales_recheck_20261006 on ports 5069/5072, with cron workers disabled.
- Verified old enabled/disabled/roleless profiles, archived and nonworking employees, missing stores and archived roles remain unchanged; existing active/locked sessions and shifts also remain unchanged.
- Verified new profiles, department-only access, missing mappings, inactive mappings, PIN validation/preservation, recoverable creation rollback, 500-employee batches and idempotency.
- Tests actively rejected writes to existing profiles and calls to close_session(). Results and rollback-only fixtures retained in /tmp/employee-sales-create-only-validation/.
- No user-facing strings changed; Arabic action translations verified at runtime for both ar and ar_001.

Rollout:

- Reload the updated Python code in the deployed Odoo process. Subsequent cron runs create missing profiles without modifying existing profiles or sessions.
- Existing means any employee access profile already present, regardless of hire date or role. Deleted profiles can be recreated when a usable mapping exists.
- This change does not restore historical flag values. No live POS cron execution or employee-data changes were performed during implementation.

commit 4e75b7e3ebfaf2d4e21516e74275f278d2cb30da
Author: hager yasser <hageryasser2002@gmail.com>
Date:   Wed Oct 7 12:18:59 2026 +0300

    ab_employee_access_sales/FIX(#20674): re-enable login for profiles with empty allowed stores

- Reenable eligible working employees even when their allowed POS store list is empty; preserve existing configured stores.
- Continue assigning exactly the department store when assigning a missing role. Missing department stores, inactive employees, terminated employment and archived roles still block login.
- Empty allowed stores retain the existing POS behavior: access to sales-enabled stores available to the service user.
- Remove the unused local allowed-store variable from synchronization.

Files changed:

- ab_employee_access_sales/changelog.d
- ab_employee_access_sales/models/ab_employee_access.py

Validation:

- Targeted ab_employee_access_sales upgrade passed in isolated codex_employee_sales_recheck_20261006 using ports 5069/5072 with cron workers disabled.
- Revised regression tests passed for empty-store reenabling, unchanged configured stores, department-scoped new assignments, missing department stores, archived/nonworking employees, session revocation, PIN preservation, savepoints, idempotency and 500-employee batches.
- Tests and results retained outside the runtime addon in /tmp/employee-sales-empty-stores-validation/; all business fixtures rolled back.
- No user-facing strings changed; existing Arabic translation entries remain applicable.

Rollout:

- Load the updated Python code in the deployed Odoo process, then run Synchronize Employee Sales Access or wait for its next scheduled run.
- No profile backfill is required. Existing empty store lists are preserved, and otherwise eligible profiles are reenabled by the cron.

commit 4380e2b5bf8821f8f007424dc05fb789d6f7e061
Author: hager yasser <hageryasser2002@gmail.com>
Date:   Wed Oct 7 09:48:02 2026 +0300

    ab_employee_access_sales/FEAT(#20674): Automatic Employee Sales Role Assignment

- Add manager-only Job Role Mappings under POS HR Configuration, with one active job-to-role selection per job and restricted reference deletion.
- Add administrator-controlled, initially inactive four-hour employee sales access synchronization. Preserve cron activation, PIN arguments and scheduling on upgrade.
- Assign only missing roles, restrict new assignments to the department store, and preserve existing roles, PINs, custom permissions and configured stores.
- Disable nonworking, archived or ineligible employee access; reenable eligible profiles, including manually disabled ones. Empty allowed stores always block automatic login.
- Revoke active and locked sessions using the existing close method and operation audit log, preserving shifts and financial records.
- Process employees in batches of 500 with per-employee savepoints, change-only writes, redacted failure logging and aggregate counts.
- Export the Odoo translation template and add both Arabic language variants for new configuration and validation strings.
- Move pre-existing development tests outside the runtime addon package; retain behavior validation scripts and results in /tmp/employee-sales-access-validation/.

Files changed:

- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d
- ab_employee_access_sales/data/employee_sales_access_cron.xml
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/models/__init__.py
- ab_employee_access_sales/models/ab_employee_access.py
- ab_employee_access_sales/models/ab_employee_access_sales_job_role_mapping.py
- ab_employee_access_sales/security/ir.model.access.csv
- ab_employee_access_sales/tests/__init__.py
- ab_employee_access_sales/tests/test_ab_employee_access_sales_api.py
- ab_employee_access_sales/views/ab_employee_access_sales_job_role_mapping_views.xml
- ab_employee_access_sales/views/menus.xml

Validation:

- Fresh install and targeted upgrade passed in isolated codex_employee_sales_access_20261006 on ports 5069/5072, with cron workers disabled.
- Verified mapping uniqueness/access, assignment and preservation, branch rejection through the POS login API, missing stores, archive/termination revocation, reenabling, PIN validation/generation, idempotency, savepoint rollback and the 500-employee boundary.
- Verified upgrade preservation of activation, code, interval and next run; installation and upgrade did not execute synchronization.
- Both Arabic files passed msgfmt --check-format; action, menu and mapping-field translations verified at runtime for ar and ar_001.
- Development database fixtures rolled back; development cron left inactive. Existing API tests were retained separately, not rerun as part of this feature validation.

Rollout:

- Configure job mappings and department stores; review existing profiles' explicit allowed stores.
- Optionally set the default_pin argument in the scheduled action. It applies only to newly created profiles.
- Have an administrator activate Synchronize Employee Sales Access. Changes apply on the next run, normally within four hours.

commit 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Jul 28 15:21:42 2026 +0300

    INIT commit pos19

- Introduce employee sales access integration with POS roles, PIN login, sessions, shifts and operation logs.

Files changed:

- ab_employee_access_sales/__init__.py
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/models/__init__.py
- ab_employee_access_sales/models/ab_employee_access.py
- ab_employee_access_sales/models/ab_employee_access_sales_operation_log.py
- ab_employee_access_sales/models/ab_employee_access_sales_pos_api.py
- ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py
- ab_employee_access_sales/models/ab_employee_access_sales_role.py
- ab_employee_access_sales/models/ab_employee_access_sales_shift.py
- ab_employee_access_sales/models/ab_sales_cashier_api_inherit.py
- ab_employee_access_sales/models/ab_sales_header.py
- ab_employee_access_sales/models/ab_sales_pos_api.py
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/models/ab_store.py
- ab_employee_access_sales/security/ir.model.access.csv
- ab_employee_access_sales/security/record_rules.xml
- ab_employee_access_sales/security/security_groups.xml
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier.scss
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier_patch.js
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier_templates.xml
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos.js
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos.scss
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_templates.xml
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return.scss
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_patch.js
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_templates.xml
- ab_employee_access_sales/tests/__init__.py
- ab_employee_access_sales/tests/test_ab_employee_access_sales_api.py
- ab_employee_access_sales/views/ab_employee_access_sales_operation_log_views.xml
- ab_employee_access_sales/views/ab_employee_access_sales_pos_session_views.xml
- ab_employee_access_sales/views/ab_employee_access_sales_shift_views.xml
- ab_employee_access_sales/views/ab_sales_header_views.xml
- ab_employee_access_sales/views/ab_store_views.xml
- ab_employee_access_sales/views/menus.xml
