---
name: odoo-security-review
description: Review Odoo ACLs, record rules, field groups, public methods, sudo and branch/company isolation for authorization changes or audits.
---

Read the diff and [project permission architecture](references/permissions.md).
Trace effective groups -> ACLs -> record rules -> field groups -> Python -> UI.

1. Build an actor matrix: ordinary user, branches A/B, manager/admin, companies
   and public/portal users if exposed. Include implied groups; check highest
   intended privilege before inherited branch roles.
2. Review XML/CSV group ladders and explicit ACL groups. Grants are additive;
   narrower ACLs cannot cancel broad grants. Keep group/membership configuration
   in security files. Check category -> privilege -> group load order.
3. Check rules per operation on headers AND lines. Global rules intersect;
   group rules allow alternatives. False rule permission flags are not denials.
   Action domains, search filters and hidden buttons are not isolation.
4. Check Python field `groups=` and direct sensitive-field reads/writes.
   `ab_smart_security_manager` is an additive overlay, not a replacement for rules
   or a way to revoke broader grants.
5. Trace public methods, imports, controllers and jobs. Validate caller, target,
   state and branch/company before mutation or scoped `sudo()`. Reject forged IDs
   and client-supplied scope. Never return unrestricted elevated records.
   Use `AccessError` for authorization and `ValidationError`/`UserError` for state.
6. Test allowed/denied ACL, row, field and method cases with normal user environments,
   including cross-branch headers/lines, inherited admin and company switching.
   Tests using `sudo()` do not prove normal-user restrictions.

Apply the security review rules in the main session. Report findings by severity,
file/line or symbol, actor, reproducible path, impact and smallest fix. Separate
missing evidence/tests from confirmed defects. Review does not authorize DB writes.
