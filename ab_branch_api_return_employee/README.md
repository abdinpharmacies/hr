# Branch API return employee validation

Install `ab_branch_api_return_employee` on the **branch server** alongside
`ab_branch_api`. This extension validates return employees before an invoice
reservation or external invoice query. API version 1 and its parameters remain
unchanged. It does not change sales, cashier routing, credentials, or permissions.

The callcenter adapter supplies `employee_ref` using the employee cost center
code. That code must identify exactly one active HR employee on the branch.
The employee's cost center must be active and have a positive `eplus_serial`.
Provision this mapping on the branch; local Odoo record IDs and callcenter
E-Plus IDs do not need to match. No mapping is created automatically and the
API key owner is not substituted for the employee.

Authentication, business ACLs and token ownership are checked first. A missing
or invalid employee then raises a correctable error while the operation is
still draft, before reservation and posting. A completed operation continues
to return its recorded result for the same payload, even if the employee is
later archived. Changed payloads, different owners/stores and uncertain
operations remain subject to the provider's existing checks.

## Callcenter companion change

The adapter change is in `/opt/odoo19/worktrees/callcenter/ab_sales`.
Upgrade `ab_sales` there after updating its files:

- POS returns use the active employee session, including its return-screen and
  store permissions. The session must belong to the executing Odoo user.
- For the standard return form, an Administrator must choose **Return Employee**
  before submitting. The selector is restricted to Settings users at the ORM
  level. An active POS session takes precedence over a form selection.
- Other users must submit through their active employee POS session.

The branch copy of `ab_sales`, `ab_branch_api`, and `ab_sales_routing` are not
modified by this change. Keep the branch API key owned by an eligible internal
non-administrator user; a callcenter Administrator may still use the form.

## Verification and rollout

1. Install this extension on a branch test database and upgrade `ab_sales` on
   the callcenter test database. Populate employee metadata through your normal
   provisioning process. Use a dedicated test E-Plus environment for real posting.
2. In the Administrator return form, submit without a Return Employee: it must
   stop locally. Choose an active employee with a matching branch cost center
   code and retry.
3. With the branch employee E-Plus serial missing, submission must stop with a
   mapping error. The branch operation must remain draft with no reservation.
4. Correct the mapping and retry the same unchanged draft. Check that the posted
   E-Plus employee is the selected employee, not the API key owner.
5. Repeat through POS: the logged-in employee must be sent. Locked/closed sessions,
   sessions belonging to another user, and forbidden stores must be rejected.
6. Retry a completed request with the same payload: no second return is posted.
   Changed payloads and cross-user/store token reuse must remain rejected.
7. Check **Return Employee** and the validation errors in both English and Arabic.

Earlier operations already marked **Needs Reconciliation** are not reset. Check
their E-Plus return and financial records and follow the existing reconciliation
process before attempting another return for the same invoice.

Implementation validation used isolated branch/callcenter database copies and
mocked E-Plus posting. No live E-Plus writes or production upgrades were run.
Development scripts and results are in `/tmp/ab_return_employee_validation`.
