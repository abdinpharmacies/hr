# Callcenter POS feedback and draft ownership

## Recent relevant commit

- Commit: c267769c3bc67e44c7af65f544ae665770b3cadd
- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-10-21 16:00:37 +0300
- Original commit subject: ab_sales/The callcenter preview exposed a missing _price_ref_from_line helper that prevents “Buy 1 get 1 free” from calculating. I’ve fixed that blocker and reruned the previews before saving the test offers
- Restored price-reference conversion for promotion previews.
- Files changed:
  - __manifest__.py
  - models/ab_sales_header.py
  - changelog.d/2026-10-21-promotion-price-reference.md

## Current changes before commit:

- Replace full-width yellow feedback with compact rounded notices. Display the submission notice only while checking, submitting, correcting or awaiting resolution; retain a clickable status badge.
- Remove the duplicate Retry button and hide the submit/retry action for Pending and Saved bills, for which the handler already does nothing.
- Group correction status, explanation, submit and cancel in one bar below the header. Hide the duplicate status badge and disabled delete control during correction; allow customer fields and totals to wrap without overlapping.
- Give delete controls a consistent rose background, a grey disabled state and rounded corners. Add translated accessible labels to the main draft-delete control.
- Scope backup errors, capacity/busy notices and conflict controls to the affected bill. Preserve an old bill’s error when switching, clear it on successful backup, and keep late responses from displaying it on a new bill.
- Fix draft backup rejection for callcenter invoices whose remote submission intentionally leaves the service-user relation empty: use the local creator as owner in that case. Preserve explicit service-user ownership, employee checks, draft-cache ownership and branch restrictions.
- Refresh existing Arabic translation references in both language files; no source terms removed.
- Show a non-sticky success toast after the branch confirms a saved return from the standard form; refresh its saved status. The dedicated return screen retains its existing success toast.
- Version is now 19.0.4.1.6 with the subsequent return-status change documented in 2026-10-22-bill-return-status.md.

Files changed:
- __manifest__.py
- models/ab_sales_branch_api_client.py
- models/ab_sales_pos_draft_slots.py
- static/src/pos/pos_action.js
- static/src/pos/pos_action.scss
- static/src/pos/pos_action.xml
- static/src/pos/zz_pos_replication_manual.xml
- i18n/ar.po
- i18n/ar_001.po
- changelog.d/2026-10-22-callcenter-pos-feedback.md

Verification:
- Simulated branch-return success produces a success notification and form refresh; pending results and exceptions never produce the form success toast. No return transactions were submitted. Targeted upgrade to 19.0.4.1.5 completed.
- Node regression checks pass for bill switching, new bills, unrelated saves, successful retry, conflicts, removed bills, late responses, flush rejection and transport errors.
- Actual pending invoice with an empty service-user relation successfully reconciles its draft; all test writes rolled back. Different employee, user, branch and explicit service-user ownership rejected. No branch API or external database writes.
- Targeted ab_sales upgrade on callcenter19 completed. Existing unrelated missing-table messages for ab_odoo_replication_override and ab_odoo_replication_override_write_rule were reported during registry initialization; outside this change.
- All installed POS template extensions compose; normal submission and correction submission are mutually exclusive, share the same safety guards, and correction actions are grouped. Full Odoo CSS bundle compiles successfully.
- Exported the Odoo POT; both Arabic PO files pass msgfmt --check-format. Runtime Bills menu differs between en_US and ar_001.
- Python/XML parsing and git diff --check pass. No connected browser was available for a visual inspection.
- Verification scripts and artifacts: /tmp/callcenter-ui (outside the addon).
