# Supplier Claim Dynamic Workflow Validation

Validated on 2026-11-15 against the local Odoo 19 runtime and PostgreSQL using
disposable databases. The validation databases were removed after completion.

## Results

| Check | Result |
| --- | --- |
| Clean installation of `ab_supplier_claim_cycle` | Passed |
| Registry/model initialization | Passed |
| XML parsing and view loading | Passed |
| Python compilation | Passed |
| Focused post-install suite | 15 tests, 0 failures, 0 errors |
| Dynamic configuration preservation rehearsal | Passed |
| `git diff --check` | Passed |

The focused tests cover:

- parallel stages and sequence advancement;
- per-stage allowed-field enforcement and attachment history;
- rejection, Secretarial correction and resubmission;
- deferral validation;
- administrator approval removal and later-stage invalidation;
- priority-ordered overlapping workflow matches requiring user selection;
- draft creation with empty, matching and invalid workflow values;
- complete submitted-workflow visibility for all department groups without expanded write access;
- reference-style claim form with dynamic header actions, workflow colors, parallel grouping,
  information cards, localized action user/date metadata, lifecycle endpoints and side chatter;
- readable history columns, wrapped detail text, semantic badges and hidden optional metadata;
- published-workflow stage renaming and additive approver/allowed-field changes,
  including propagation to existing claims;
- published-workflow domain, sequence, stage-structure and relationship-removal guards;
- allowed-field selector filtering aligned with server-side publication validation;
- fully editable draft copies created by **New Version**;
- unassigned-participant record-rule denial;
- absence of hardcoded department lifecycle methods and obsolete wizard models.

The isolated `hr_db` clone retained identical counts and content hashes for 190
claims, 7 workflows, 29 stages, 19 runtime stage states, 195 allowed-field links,
58 approver links, 86 history rows and 25 document rows after the targeted upgrade.

## Deployment

Before production, restore the production backup into an isolated database and run
the targeted module upgrade with the production addons path. Compare claim,
workflow, stage, approver, allowed-field, history and document snapshots before
and after the upgrade. Do not use `-u base`.

```bash
odoo-bin -c /path/to/isolated.conf -d supplier_claim_test \
  -u ab_supplier_claim_cycle \
  --test-enable --test-tags=/ab_supplier_claim_cycle \
  --stop-after-init
```

No Telegram module is part of this validation or release.
