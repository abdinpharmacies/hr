# Supplier Claim Cycle

Odoo 19 · version 19.0.7.1.0 · Developer: Alhassan Hossny

## Dynamic workflow

Supplier claims use versioned, administrator-configured workflows instead of
hardcoded departments. A workflow contains a literal claim domain, a display
priority and ordered stage lines. Stages with the same sequence run in parallel.

Each stage defines:

- the internal users who may decide it;
- the claim fields those users may edit while the stage is pending or deferred;
- its sequence within the workflow.

Workflow priority orders matching choices. When exactly one published workflow
matches a saved draft it is selected automatically. When several match,
Secretarial must select one before submission. Submission revalidates the domain.

On a published workflow, administrators may rename a stage and add approvers or
allowed fields. Those additions apply immediately to every claim that references
the stage. Existing approvers and allowed fields cannot be removed, and the
domain, priority, sequence and stage structure remain immutable. Use **New
Version** for those structural changes. Archived versions are fully immutable.

## Runtime behavior

Submission creates one runtime stage-state row for every configured stage. The
first sequence becomes pending and later sequences wait. A sequence advances only
after every parallel stage is approved. The final approval closes the claim.

Any configured approver can complete a stage. Claim Administrators can decide any
active stage. Rejection returns the claim to Secretarial, which may edit the same
fields granted to the rejecting stage. Resubmission reopens that stage and retains
approved parallel siblings. Deferral requires a reason and a current or future
follow-up date.

Claim Administrators may remove an approval from an open claim with a mandatory
reason. The selected stage reopens, approved siblings in its sequence remain, and
all later decisions are invalidated. Closed claims are immutable.

Allowed-field rules are enforced by the ORM; form readonly modifiers are only the
presentation layer. Binary fields also grant their conventional filename field.
Uploads continue to create immutable document-history records.

## Security

- **Secretarial** creates drafts, selects workflows and handles returned claims.
- **Workflow Participant** reads assigned claims and their complete workflow, history,
  documents, and supplier details. Only an assigned active-stage approver can edit
  that stage’s allowed fields or decide it.
- **Reviewer** has read-only access.
- **Administrator** configures workflows, overrides active decisions and removes
  approvals.

These are the only four supplier-claim groups. Department responsibilities belong
to workflow stages; there are no department-specific security groups.

Participants can read claims assigned to any of their snapshot stages. Company
record rules still restrict claim, stage-state, history and document access even
though workflow definitions are globally shared.

## Deployment

Upgrade an existing dynamic installation with the targeted module upgrade, not an
uninstall/reinstall. Version 19.0.7.1.0 migrates effective department-group members
(including inactive users) to Workflow Participant, then removes department ACLs,
rules and groups. The four retained XML IDs and all business records stay intact.
Unknown custom dependencies stop the upgrade instead of being silently removed.
Participants lose the former department-wide submitted-claim visibility and see
only assigned claims. Reviewer remains read-only, including when also assigned
as an approver, unless the user is an Administrator.

```bash
odoo-bin -c /path/to/instance.conf -d existing_database \
  -u ab_supplier_claim_cycle --stop-after-init --no-http
```

`tools/audit_security_upgrade.py` captures read-only row fingerprints and role
memberships for before/after comparisons. It does not store record contents or
create a database/filestore backup. Do not run fixture-based module tests against
an actively used database; use static/unit checks plus read-only access checks for
an in-place upgrade.

The standalone transfer tools support legacy 19.0.4.x and dynamic 19.0.7.x bundles
with a 19.0.7.1.0 target. Department roles in historical bundles map to Participant;
they are not recreated. This does not add a direct hardcoded-to-dynamic module
upgrade path: legacy claim data still requires the documented transfer tooling.

No Telegram adapter or Telegram compatibility layer is included.

## Validation

The focused suite covers domain matching and priority, parallel progression,
allowed-field enforcement, immutable document snapshots, rejection/resubmission,
deferral, approval removal, closed-claim protection, participant record rules,
published-version editing guards and removal of fixed department routing.
