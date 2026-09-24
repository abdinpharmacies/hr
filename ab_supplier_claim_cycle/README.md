# Supplier Claim Cycle

Self-contained Odoo 19 workflow. The original `supplier_claim_group_user` XML ID
now represents Secretarial; reviewer and administrator XML IDs are retained.

Cash: Secretarial → Supplier Accounts → Secretarial closure.
Non-cash: Secretarial → Inventory and Purchasing (parallel) → Supplier Accounts
→ Bank Accounts → Secretarial closure.

Department notes supply the reason for Reject and Defer. Defer also requires a
follow-up date today or later. A deferred review remains in that department's
queue. Non-cash Supplier Accounts approval requires an uploaded cheque.

Supplier payment nature, business category, and the existing `tax_type` are
snapshotted on first submission. Tax classification never routes a claim.
The supplier cannot be replaced after submission. Returned claims allow
Secretarial to correct invoice details and resubmit; classification snapshots
remain unchanged. Every resubmission increments the review round. Parallel
rejections restart both reviews; later rejections resume at the rejecting stage.

Reviewers can read all claims. Departments can read claims assigned to them,
including their completed reviews, but can only act on their own pending or
deferred decision in the current stage. This preserves access to action results
and review history after the claim advances. Queue menus show current work only.
Administrators follow the same state-machine validations and may perform every
role's actions. Closed claims allow archive/restore only, including for admins.
History records are append-only and contain decision snapshots at every event.
Cheques are stored on the claim to enforce its write protections on the evidence.

## Deployment prerequisites

This replacement assumes **zero existing claims**. It changes `supplier_id` from
`ab_costcenter` to `ab_supplier` and replaces the old status field. Do not apply it
to a database containing old claims without a separately designed migration.

`ab_supplier_claim_workflow` must remain uninstalled. Its automatic-install
setting makes a full custom-addons directory unsafe for this deployment. Build a
curated addon directory containing only the deployed modules and dependencies,
**excluding that module and addons depending on it**, and configure `addons_path`
to use the curated directory. Do not also include the original unrestricted
custom-addons directory. Confirm the conflicting module is uninstalled and not
scheduled for installation before updating. This module does not import or
modify the conflicting addon and cannot enforce another deployment's addon path.

Back up the target database, stop its workers, and run only:

```sh
/path/to/venv/bin/python /path/to/odoo-bin -c /path/to/curated.conf \
  -d TARGET_DATABASE -u ab_supplier_claim_cycle --stop-after-init
```

Do not upgrade `base`. Restart workers after the targeted upgrade.

## Validation

Run tests on an isolated database with the same curated addon path:

```sh
/path/to/venv/bin/python /path/to/odoo-bin -c /path/to/curated.conf \
  -d TEST_DATABASE -u ab_supplier_claim_cycle --stop-after-init \
  --test-enable --test-tags /ab_supplier_claim_cycle
```

The suite covers routing, snapshots, approvals in both orders, rejection and
resubmission, deferrals, cheque evidence, closure, archival, immutable history,
all roles, view/button restrictions, form creation, and forged ORM writes.

## Deployed environment (2026-09-23)

The clean module is deployed to `abdin_replica19`. The runtime configuration at
`/opt/odoo19/odoo19.conf` uses `/opt/odoo19/server/addons` and the curated custom
addon path `/opt/odoo19/deployment-addons/supplier-claims-clean`. The recovery
addon path is no longer active. The two legacy claim addons are excluded from
the curated path, remain uninstalled, and have automatic installation disabled
in module metadata. New custom addons must be deliberately added to this
curated path; do not replace it with the unrestricted custom-addons directory.

The database was backed up before the targeted upgrade under
`/opt/odoo19/codex-backups/scc-clean-20260923-132826/`. All 15 tests passed on a
restored copy of this database. Live cash and non-cash smoke checks passed and
were rolled back, leaving no verification suppliers or claims behind.
