# Supplier Claim Cycle

Self-contained Odoo 19 workflow. The original `supplier_claim_group_user` XML ID
now represents Secretarial; reviewer and administrator XML IDs are retained.

Cash: Secretarial → Supplier Accounts → Secretarial closure.
Non-cash: Secretarial → Inventory → Purchasing → Supplier Accounts
→ Bank Accounts → Secretarial closure.

Department notes supply the reason for Reject and Defer. Defer also requires a
follow-up date today or later. A deferred review remains in that department's
queue. Non-cash Supplier Accounts approval requires an uploaded cheque.

Supplier payment nature and business category are snapshotted on first submission.
Optional Tax Type and Section default from the supplier and remain editable in Draft;
submission freezes them. Tax classification never routes a claim.
The supplier cannot be replaced after submission. Returned claims allow
Secretarial to correct invoice details and resubmit; classification snapshots
remain unchanged. Every resubmission increments the review round. Resubmission resumes the rejecting stage and preserves earlier approvals.

Reviewers can read all claims. Departments can read claims assigned to them,
including their completed reviews, but can only act on their own pending or
deferred decision in the current stage. This preserves access to action results
and review history after the claim advances. One All Claims menu shows every
claim allowed by the existing read permissions, including completed reviews.
Legacy queue actions remain available, but their menus are inactive.
Department actions appear in the form header as Approve, Reject, and Defer.
The native statusbar shows sequential stages. Department fields are visible only
in their current stage; shared metadata remains visible as plain fields. There
are no custom cards, timelines, or collapsed sections. Only Stage History is tabbed.
Administrators follow the same state-machine validations and may perform every
role's actions. Closed claims allow archive/restore only, including for admins.
History records are append-only and contain decision snapshots at every event.
Cheques are stored on the claim to enforce its write protections on the evidence.

## Deployment prerequisites

The original 19.0.2.0.0 replacement required zero claims from the old schema.
Version 19.0.2.1.0 supports existing 19.0.2.0.0 claims through its versioned
post-migration. It does not migrate the earlier `ab_costcenter` supplier schema.

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

The suite covers routing, snapshots, sequential approvals, rejection and
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


## Reverification (2026-09-24)

The deployed source matches this module through the curated addon symlink.
`ab_supplier_claim_cycle` is installed at `19.0.2.0.0`; both conflicting workflow
addons remain uninstalled with `auto_install=False` and excluded from the runtime
addon path. No conflicting addon files were changed.

A fresh backup of `abdin_replica19` was restored as `scc_verify_20260924`, with a
separate filestore copy. A targeted `-u ab_supplier_claim_cycle` and all **18 tests
passed with zero failures and zero test errors**. No base upgrade was run.
The additional regression tests cover every rejection route through closure,
all department permission/queue combinations, and both routes under module and
system administrators. Existing tests cover snapshots, supplier lookup/defaults,
parallel approval order, required reasons/dates/cheques, immutable closed claims
and history, archival, forged writes, and Odoo form/view/button validation.

Rollback-only verification on `abdin_replica19` used the ten sample suppliers:
five cash and five non-cash claims all reached `closed` in review round 2 after
Supplier Accounts rejection and Secretarial resubmission. Non-cash claims also
exercised Inventory deferral, both parallel approvals, cheque evidence, and Bank
Accounts approval. Separate temporary department users performed each action;
Secretarial performed final closure. Cash histories contained six events and
non-cash histories ten. All verification records/users were rolled back.
The existing claim and all ten supplier/cost-center assignments were verified
unchanged. The zero-existing-claims prerequisite is historical: there is now one
claim, so a destructive reset or legacy-schema migration must not be attempted.

Only tests and this documentation changed; no production workflow fix or live
upgrade was necessary. Upgrade verification was performed on the isolated copy.
No browser interaction test was performed; UI coverage uses Odoo's form helper,
compiled views per role, button restrictions, and queue domains.

Evidence and the pre-test backup are in `/tmp/scc-verification-20260924/`:
`tests-final.log`, `live_smoke.log`, `live_smoke.py`, and
`abdin_replica19.backup`. This is temporary storage, not backup retention.
The isolated test database is retained for inspection.

Unrelated environment issues remain: Odoo reports `ab_invoice_direct_print`
and `payroll_test` as not loadable, plus legacy configuration/API warnings in
other modules. They did not fail these claim tests and were not modified.


## Simplified claims UI (2026-09-24)

Department decisions are in the form header with explicit department labels.
All review fields appear below Rejection Reason; only Stage History remains in
the notebook. All authorized roles share All Claims, governed by the existing
record rules. Completed claims remain visible; archived claims use the Archived
filter. The five legacy queue menus are inactive, retaining their XML IDs.

The targeted upgrade and all 19 tests passed on `scc_verify_20260924`, including
compiled forms for every role, menu visibility, and continued claim visibility
through submission, deferral, rejection, approval, closure, and archival.
Evidence: `/tmp/scc-ui-tests-final.log`. Browser visual verification was not run.

Deployment still requires a targeted upgrade on the live database. Include
`--i18n-overwrite` with `-u ab_supplier_claim_cycle` so the existing Arabic menu
translation changes to `مطالبات الموردين`. Back up first and follow the worker
shutdown/curated-addon procedure above. No live database upgrade was performed
for this UI change.


## Shipment-style timeline refinement (2026-09-24)

The form now uses a module-scoped XML/SCSS timeline, with Inventory and Purchasing
shown in parallel. Cash claims omit those reviews and Bank Accounts; draft claims
explain that routing is determined on submission. Text labels distinguish
approved, pending, deferred, rejected, cancelled, and not-required decisions.
Returned claims show the rejection reason in a correction banner.

Current Review expands only pending/deferred department fields. Review Details
contains read-only copies of other applicable reviews. Additional Information
contains creator, review round, and classification metadata. Both disclosures
start collapsed. Existing role-based edit/action permissions remain unchanged;
admins retain both parallel department button sets. List decision columns and
review round are optional and hidden by default. Timeline dates are read-only.

All **20 tests passed** following an isolated targeted upgrade with translation
overwrite; log: `/tmp/scc-timeline-tests-final.log`. SCSS compiles successfully.
The added display test covers parallel partial approval, return for correction,
cash routing, closure, read-only history, and six parallel admin actions.
English/Arabic translations and responsive/RTL styling are included. No browser
provider is available in this session, so desktop/mobile screenshot and browser
interaction verification remain outstanding. No live upgrade was performed.


## Sequential stages — 19.0.2.1.0 (2026-09-24)

This release supersedes the parallel workflow and UI descriptions in the dated
notes above. Inventory and Purchasing are separate stages, including backend
permissions, record rules, search filters, and legacy queue actions. Purchasing
rejection returns to Purchasing after correction and preserves Inventory approval.
Cash routing, evidence requirements, immutable history, and closure remain intact.

The form uses native statusbars and plain XML groups. Only the current department's
fields and authorized decision buttons appear. Cheque fields appear in Supplier
Accounts; rejection fields appear on return to Secretarial. Shared claim metadata
and Stage History remain available. Custom timeline/card/disclosure SCSS is removed.

The migration preserves decisions, attachments, archived claims, and all historical
rows. It appends a migration audit event and routes outstanding combined reviews
to Inventory, Purchasing, or Supplier Accounts based on existing approvals. A
Purchasing approval already recorded by the parallel workflow remains valid.
Returned combined reviews resume at the rejecting department. Inconsistent
records stop the transaction before changes are applied. In particular, an old
Purchasing rejection with unapproved/cancelled Inventory requires an explicit
business resolution; the migration never invents an approval or skips Inventory.
The legacy combined-state label remains readable in old history.

Validation: targeted upgrade on `scc_verify_20260924`; all 21 tests passed
with zero failures and errors. Coverage includes both routes, all roles, migration,
and compiled English/Arabic form visibility. Log: `/tmp/scc-sequential-tests-final.log`.
No connected browser was available for visual verification. No live database
upgrade or worker restart was performed. Deploy with a backup, stopped workers,
the existing curated addon path, and a targeted `-u ab_supplier_claim_cycle`
upgrade with `--i18n-overwrite`; then restart workers. Do not upgrade `base`.


## Legacy supplier-reference recovery (2026-09-27)

The pre-migration retains the raw legacy supplier reference and status before
Odoo creates the new supplier relation. The post-migration distinguishes true
cost-center claims from newer claims whose schema was rolled back: a matching
new-workflow `created` audit event (within one second of the claim creation time)
is required before retaining a native supplier ID. Missing original suppliers
or conflicting audit identities stop the transaction rather than remapping IDs.

For true legacy references, suppliers are resolved by `costcenter_id`. Missing
suppliers are created through the ORM from the source cost-center name/code and
contact details. Duplicate name/code candidates or multiple links stop recovery.
No records are deleted, existing suppliers are not renamed or reclassified,
and financial amounts are unchanged. Creation uses the module's default
non-cash/other classifications and leaves tax classification unspecified.

Matching audit histories restore the latest stage, decision snapshots, review
round, department notes, and historical cash/non-cash route. An earlier
`migrated` audit event does not cause recovery to be skipped. Each claim receives
a new recovery audit entry and a transactionally stored idempotency marker.
The original reference, its resolved model, and the old status remain available
in the database for traceability. The new Supplier foreign key and NOT NULL
requirement are enforced before the upgrade commits.

Claims without department audit evidence enter **Legacy — Review Required**;
the original status (for example `sign_check`) stays visible. No approvals are
invented and these records cannot close directly. Only an existing module
administrator can select **Restart Legacy Review** to return the claim to Draft
for the normal approval workflow; the source status and history remain intact.

Back up before a targeted `-u ab_supplier_claim_cycle`. Do not upgrade `base`.
Rehearse on a restored copy before upgrading a database with mixed-schema data.


## Supplier classifications and brackets — 19.0.2.2.0

Tax Type and Section are optional draft fields. Supplier master values take
precedence; if a master field is empty, its first non-empty submitted claim choice
becomes that supplier's fallback. Drafts and later overrides never replace this
fallback. Explicit empty choices remain empty. Defaults are recorded in a protected
module-owned model, without writing supplier master data. Supplier locks and Odoo
transaction retries protect concurrent first submissions. Batched creates resolve
supplier defaults together; batched submissions use claim ID order for first choices.

Tax choices retain their keys and display in Arabic as دفعات مقدمة، ضريبي، غير ضريبي.
Sections are تجميل، أدوية، مستلزمات، مستورد أدوية، مستورد تجميل، مستحضرات طبية;
the legacy Other choice remains available. Existing submitted records are not
reclassified and historical section values are not fabricated.

A claim can select an optional bracket belonging to its supplier's cost center.
The domain and backend both enforce this relationship. Drafts preview payment
terms; submission stores payment type, start/termination days, credit days,
discount, and withdrawal bracket in an immutable snapshot and the audit event.
Neither bracket selection nor classification changes calculate claim amounts or
change approval routing. Changing supplier clears the old bracket; selecting a
valid new bracket in the same form save is supported. Brackets cannot be deleted
while referenced by claims. Claim roles can read eligible brackets, but gain no
bracket or cost-center editing permissions.

The inherited form groups Supplier & Classification, Claim Details, Payment Terms,
Notes, and Reference above the existing department review and history areas. It
uses native Odoo controls, responsive groups, Arabic labels, and optional list
columns. No shared frontend component or JavaScript was modified.

The existing recovery migration now skips completed recovery metadata before
reading obsolete legacy status columns. Its tests support restored databases
that already retain these metadata columns. This does not rerun or alter completed
recovery on a 19.0.2.1.0 database.

Replica sample setup is a one-time administrator ORM operation, not addon demo
or manifest data. Six isolated sets use codes SCCS26092701–SCCS26092706 and names
prefixed [SAMPLE]. Each contains a supplier, cost center, bracket, and draft claim.
Three suppliers have empty master classifications for testing first-choice defaults.
The replica's normal cost-center creation restriction stays enabled; only the six
sample cost-center creations use the existing initialization context. No external
writes, inventory operations, prices, payments, or approvals are generated.


Deployment and verification (2026-09-27): `abdin_replica19` is running
19.0.2.2.0 following a targeted upgrade and application restart. All **32 tests**
passed on `scc_terms_verify_20260927`, including English/Arabic compiled views,
form creation and supplier changes, access checks, bracket snapshots, multi-record
submission, and legacy recovery. Separate two-transaction checks passed for both
overlapping submissions and stale snapshots. Sample setup was run twice on the
isolated database and retained the same six sets.

The live sample claim IDs are **22–27**, with bracket IDs **1–6**. All remain Draft.
A comparison of every original database column verified that the 11 existing
suppliers, 10,374 cost centers, nine claims, and 46 history records were unchanged.
The live application returned HTTP 200 after restart. Browser desktop/mobile
visual inspection was unavailable because no browser provider was connected.

Database and filestore backups, previous staged source, implementation snapshot,
upgrade logs, scripts, and verification evidence are retained at:
`/opt/odoo19/codex-backups/scc-terms-20260927/`.
The isolated test database is retained for inspection. No commit was created.


## Stage History simplification — 19.0.2.2.1

Creating and initially submitting a claim no longer creates Created or Submitted
history events. Stage History starts with the first department decision.
Resubmissions, decisions, closure, archive/restore, and migration events remain
recorded. Previously stored Created and Submitted events are excluded from the
history relation, preserving old recovery evidence without showing those rows.
Classification and bracket snapshots still freeze on first submission and appear
in subsequent decision audit snapshots. No existing history records are deleted.

Validation: all **33 tests passed** on the isolated replica, including no history
rows on draft creation or initial submission, retained department/resubmission
events, hidden legacy automatic rows, and old-schema migration fixtures.


## Claim form — 19.0.2.2.2

Removed the Reference section and its User / Review Round fields from the claim
form. Backend ownership and review-round tracking remain available to the workflow
and Stage History.


## Claim form — 19.0.2.2.3

Removed the Payment Terms section, bracket selector, and term previews from the
claim form. Existing bracket records, claim links, and submitted snapshots are
preserved.


## Supplier boundary — 19.0.2.3.0

The claim module depends on `ab_supplier` for supplier business data, with no
direct `ab_costcenter` dependency. Core Odoo dependencies (`base`, `mail`, and
`web`) remain. The supplier module owns bracket ownership/domain resolution and
legacy supplier-reference mapping; claim code delegates to those supplier methods.
The unused cost-center UI helper field is removed.

`ab_supplier` still depends on `ab_costcenter`, so it remains installed indirectly.
The historical pre-migration script retains recognition of the old cost-center
foreign key; its fixtures intentionally reproduce that old schema. These are
legacy recovery safeguards, not normal claim data access. Existing supplier links,
classification defaults, bracket snapshots, and claim history are preserved.

Deployed to `abdin_replica19` on 2026-09-27 with a targeted
`-u ab_supplier,ab_supplier_claim_cycle`. All **33 tests passed** on the isolated
replica. Live dependency metadata is `ab_supplier`, `base`, `mail`, `web`;
supplier links and bracket validation were verified through the supplier API.
Existing supplier, cost-center, bracket, claim, history, and defaults records
were compared before/after and preserved. Odoo returned HTTP 200 after restart.
Backups and test/deployment logs are in
`/opt/odoo19/codex-backups/scc-supplier-boundary-20260927/`.


## Secretarial notes in history — 19.0.2.4.0

Removed the standalone Notes section and its Secretarial Notes textarea. Secretarial
users and administrators use **Add Secretarial Note** in Draft or Returned to
Secretarial. The XML dialog saves an immutable history row showing the department,
note, author, and timestamp in Notes / Reason. It does not change the stage or
create automatic Created/Submitted rows. Opening and saving both validate current
access and stage, so stale dialogs cannot add notes after the claim advances.

The old notes field remains for compatibility. Explicit non-empty notes supplied
through create/write also append history; unchanged or blank values do not create
rows. The migration imports existing user notes once, including closed/archived
claims, using an Imported Secretarial Note event and the actual import date/actor.
Original claim fields and history rows remain unchanged. The six exact generated
training labels are excluded from the import.

All **36 tests passed** on the isolated replica, covering the dialog, role/stage
restrictions, immutable notes, API writes, English/Arabic compiled forms, workflow
behavior, and idempotent historical-note import.

Deployed to `abdin_replica19` on 2026-09-28. Five existing user notes were imported;
the generated sample labels were excluded. All original supplier, cost-center,
bracket, claim, history, and defaults rows were preserved. Live rollback-only
verification confirmed the Arabic/English Notes / Reason column and successful
note-dialog logging with author/date, without leaving test records. Backup and
verification logs: `/opt/odoo19/codex-backups/scc-secretarial-history-20260928/`.


### Payment Nature — 19.0.2.5.0

Payment Nature is visible beside Tax Type and Section in Draft, with Arabic
choices نقدي and غير نقدي. Saving an explicit selection remembers it on the
supplier for future claims. Each existing claim retains its own selection.
Secretarial users and administrators can change it only in active Draft claims;
submission uses that selection and freezes it through returns and resubmission.
Older drafts with no saved payment nature must select one before submission.
No existing supplier preferences or submitted claim routes are migrated.

Deployed to `abdin_replica19` on 2026-09-28 after all 39 module tests passed.
Live rollback-only verification confirmed the Arabic choices, saving the supplier
preference, reuse by new claims, and preservation of the submitted claim's route.
All existing business rows were unchanged by the targeted upgrade. Backup and
verification logs: `/opt/odoo19/codex-backups/scc-payment-nature-20260928/`.
