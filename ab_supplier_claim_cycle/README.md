# Supplier Claim Cycle

Odoo 19 · version 19.0.6.6.0 · Developer: Alhassan Hossny

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
- **Workflow Participant** is required for users configured as stage approvers.
- **Reviewer** has read-only access.
- **Administrator** configures workflows, overrides active decisions and removes
  approvals.

Participants can read claims assigned to any of their snapshot stages. Company
record rules still restrict claim, stage-state, history and document access even
though workflow definitions are globally shared.

## Upgrade from 19.0.5.x

Back up PostgreSQL and the matching filestore, then rehearse the targeted upgrade
on an isolated restored database before production.

The `19.0.6.0.0` migration:

- creates immutable legacy workflow versions for cash/non-cash and tax/non-tax
  routes;
- adds existing departmental approvers to Workflow Participant;
- converts draft, open, returned and closed claims to runtime stage-state rows;
- preserves existing chatter, history, documents, XML IDs and legacy audit data.

Run only the targeted module upgrade:

```bash
odoo-bin -c /path/to/isolated.conf -d supplier_claim_test \
  -u ab_supplier_claim_cycle \
  --test-enable --test-tags=/ab_supplier_claim_cycle \
  --stop-after-init
```

No Telegram adapter or Telegram compatibility layer is included.

## Validation

The focused suite covers domain matching and priority, parallel progression,
allowed-field enforcement, immutable document snapshots, rejection/resubmission,
deferral, approval removal, closed-claim protection, participant record rules,
published-version immutability and legacy migration.
