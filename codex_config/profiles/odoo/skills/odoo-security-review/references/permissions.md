# Permission Architecture

Project source: AGENTS.md. Verified semantics: https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html . Review effective access, including inherited groups, for normal users rather than sudo environments.

### Project Permission Architecture Reference

Permission design in this repository is layered and module-owned. Apply the
layers in this order when designing or reviewing access:

```text
User
  -> direct groups + implied groups
  -> model ACLs (read/write/create/unlink)
  -> record-rule domains
  -> field-level group restrictions
  -> Python workflow and scope validation
  -> menu/view/button visibility
```

The UI layer is not a security boundary. A hidden menu, page, field, or button
must always be backed by ACLs, record rules, field groups, or Python validation
because records and methods may still be reached through imports, RPC, server
actions, or other model code.

#### Group Design

- Define `ir.module.category`, then `res.groups.privilege`, then `res.groups`.
- Build explicit role ladders with `implied_ids`, for example User -> Manager ->
  Administrator.
- Give every ACL an explicit group. Do not leave `group_id` empty.
- Do not imply a business role from `base.group_user` unless every internal user
  is intentionally meant to receive that role.
- If `base.group_system` implies a module administrator group, remember that
  Settings users inherit every lower group in that chain. Check the highest
  privilege first in Python, as described in Development Rule 7.
- Keep operational roles separate when they are not hierarchical. For example,
  a branch receiver and a requester may be independent roles while a manager
  may intentionally imply both.

#### ACL Semantics

ACLs answer whether a user may perform an operation on a model at all.

- ACL grants are additive across all effective groups. A restrictive ACL does
  not cancel a broader grant from another group.
- Absence of an ACL grant denies that model operation.
- Prefer a minimum matrix: read-only for reference users, bounded create/write
  for operational users, and unlink only for explicitly authorized roles.
- Critical pharmacy records should normally be archived, not granted unlink.
- Review inherited groups when evaluating effective ACLs; checking only the
  group directly assigned to the user is insufficient.

#### Record Rule Semantics

Record rules restrict which rows remain accessible after the ACL check.

- If an ACL grants an operation and no applicable record rule restricts it, all
  records of that model are accessible for that operation.
- Global rules intersect with all access. Group rules are combined as allowed
  alternatives and then intersected with global rules.
- `perm_read`, `perm_write`, `perm_create`, and `perm_unlink` on an `ir.rule`
  indicate the operations for which its domain applies; a false flag is not an
  explicit denial.
- Use record rules for stable row ownership and isolation such as user,
  requester, assigned employee, department, branch/store, workflow participant,
  and `company_ids`.
- Branch-sensitive models must include branch filtering on parent and child
  models. A secure header with unrestricted lines can still leak branch data.
- State-dependent write domains should be paired with Python validation so that
  a crafted direct method call cannot bypass the business transition rules.
- Provide an explicit unrestricted manager/administrator rule only when that
  role is intended to see every row.

Typical project pattern:

```text
Requester -> own requests
Branch Receiver -> assigned branch records in active states
Department Manager -> managed/assigned department records
Manager/Administrator -> all records
```

#### Field Security

- Protect sensitive fields with the Python field `groups=` attribute. XML
  invisibility alone is not sufficient.
- Apply field groups to salary, payment details, credentials, integration
  tokens, private contact data, and raw external payloads as applicable.
- A user who can read a model should not automatically receive every sensitive
  field on that model.
- When using `ab_smart_security_manager`, treat it as an additive role/ACL and
  field-access overlay. It does not replace module record rules and cannot
  revoke access already granted by a broader ACL from another group.

#### Python Authorization and `sudo()`

- Use Python checks for workflow actions, state transitions, branch assignment,
  and invariants that cannot be represented safely by a static record domain.
- Raise `AccessError` for authorization failures and `ValidationError` or
  `UserError` for business-state failures as appropriate.
- Never rely on a computed UI flag such as `can_edit` as the only enforcement;
  repeat the authorization check inside the invoked method.
- Treat `sudo()` as a scoped privilege escalation. Validate the caller, role,
  branch/company scope, and target records before calling it.
- Keep elevated recordsets local to the smallest required operation. Do not
  return unrestricted `sudo()` recordsets to normal-user code.
- Public controllers and integration jobs must authenticate or validate their
  own scope before using `sudo()` because normal ACLs and record rules are then
  bypassed.

#### Permission Review Checklist

For every new or changed business model, verify:

1. The group hierarchy and all inherited groups are intentional.
2. The ACL matrix covers read/write/create/unlink with least privilege.
3. Ordinary users cannot read another user's records unless intended.
4. A branch user cannot read or modify another branch's header or line records.
5. Company-scoped models use the allowed company set where applicable.
6. Managers and administrators receive the intended broader access without
   being trapped by inherited lower-role checks.
7. Sensitive fields are unavailable through direct ORM reads for unauthorized
   users, not merely hidden in views.
8. Workflow methods reject unauthorized direct calls.
9. Every `sudo()` path preserves user, branch, company, and record scope.
10. Tests cover one allowed and one denied case for ACLs, record rules, field
    access, and critical workflow methods.

When auditing an existing module, distinguish a UI action domain or search
filter from a real record rule. Action domains improve navigation but do not
provide row-level security.

