# Supplier Claim Cycle

Odoo 19 · version 19.0.7.2.5 · Developer: Alhassan Hossny

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

An unused published workflow can return to Draft for full editing and must be
published again before use. Once used by a submitted claim (including returned,
closed or archived claims), its domain, priority, sequence and stage structure
remain fixed. Administrators may rename stages and add or remove approvers and
allowed fields. Each stage must retain at least one valid approver. Removed
approvers retain read-only access to previously assigned claims; current
approvers alone can decide stages and edit allowed fields. Allowed-field removals
apply immediately to current, future and returned stages. Archived versions are
immutable. Use **New Version** for structural changes to used workflows.

**Reset to Draft** is visible on every published workflow. For used workflows,
clicking it explains why the reset is blocked and directs the administrator to
**New Version**. Submission snapshots keep this protection in place even when a
claim is reset to Draft.

Archiving sets the workflow to Archived and inactive. Unarchiving a used workflow
restores the same version to Published and active, making it available for new
matching claims without changing existing claim history. An unused workflow
returns to Draft and active; its linked draft claims have their workflow selection
cleared, including archived drafts. Unarchive never creates a new version; use
**New Version** explicitly when an editable copy is needed.

## Draft route templates

The module seeds 12 **Draft** workflows: Medicine (01–06) and Cosmetics (07–12),
with tax/non-tax routes for bank transfer, northern cheque delivery and southern
cheque delivery. Each route is fully sequential. Tax routes include Tax Accounts
and Supplier Accounts After Tax; non-tax routes omit both. Cheque routes include
Cheque Treasury, followed by Upper Egypt Supplier Accounts for southern delivery.
Every route ends with Secretarial Closure.

Matching uses Section (`medical` / `cosmo`), Tax Type (`tax_payment` /
`non_tax_payment`), Payment Nature (`bank_transfer` / `check`) and, for cheques,
Area (`north` / `south`). Transfers match either area. Advance Payments
(`through_supplier`), Cash, Check and Transfer, and Other purchases are outside
these templates. Existing overlapping published workflows remain unchanged.

Administrators must assign active Workflow Participants as approvers and configure
any editable fields before publishing. The templates initially have neither
assignment; drafts cannot be selected for claim submission. English source names
and standard Odoo Arabic PO translations cover all workflows and stages.

Seed XML uses `noupdate="1"`: module upgrades create missing seed records without
resetting existing administrator edits or publication states. Future changes to
existing seed configuration require explicit administrator edits or a new workflow
version, rather than changing XML alone.

## Claim entry and attachments

Drafts may be incomplete. Initial submission requires supplier, area,
representative phone and name, explicit contact confirmation, invoice type and
count, claim amount and date, section, payment nature and tax type.
Claim Month uses the standard Odoo calendar with field-local ISO (`YYYY-MM-DD`)
entry and display, preserving the selected day. Other date formats are unchanged.
Supplier defaults include representative contact details from the latest claim,
including archived claims. Confirmation and claim month are not inherited.
Changing contact details resets confirmation unless explicitly confirmed again.

Tax Discount Amount and Net Claim Amount are normal editable draft entries;
neither is calculated automatically. Tax Discount Rate has been removed. A
persistent, non-blocking warning appears across stages when a nonzero discount
makes Claim Amount minus Tax Discount Amount differ from Net Claim Amount.
The Taxes and Amounts tab precedes Documents and Notes.

All dedicated attachment fields are visible and optional. A participant may
upload one file to an empty field allowed in their active stage. Saved attachments
cannot be replaced, renamed, cleared or deleted by participants. Additional files
belong in Chatter, which is available to every participant who can access the
claim, regardless of active-stage field permissions. Saved Chatter attachments
are also protected. Existing administrator/secretarial privileges are preserved.

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

Participants can read claims assigned to any of their historical stage memberships. Company
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
