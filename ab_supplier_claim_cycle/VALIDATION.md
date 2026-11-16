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
| Legacy open-claim migration rehearsal | Passed |
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
- conversion of a legacy open claim into runtime stage-state rows.

## Deployment

Before production, restore the production backup into an isolated database and run
the targeted module upgrade with the production addons path. Compare claim,
history and document counts before and after the upgrade. Do not use `-u base`.

```bash
odoo-bin -c /path/to/isolated.conf -d supplier_claim_test \
  -u ab_supplier_claim_cycle \
  --test-enable --test-tags=/ab_supplier_claim_cycle \
  --stop-after-init
```

No Telegram module is part of this validation or release.
