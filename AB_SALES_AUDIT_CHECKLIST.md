# Callcenter and Branch Sales Audit Checklist

Audit baseline: 2026-10-13. Track functional fixes and regression tests for callcenter and branch `ab_sales`. Security review is outside scope. Check items only after verification; implementation alone does not mark an item complete.

## Environment

| System | Workspace | Dev URL | Database |
| --- | --- | --- | --- |
| Callcenter | `/opt/odoo19/worktrees/callcenter` | `http://127.0.0.8:5066` | `callcenter19` |
| Branch POS | `/opt/odoo19/custom-addons` | `http://127.0.0.8:4092` | `abdin_old_pos19` |

Configurations: `/opt/odoo19/odoo19-callcenter.conf` and `/opt/odoo19/odoo19-pos.conf`. The active callcenter connection targets the branch above; the configured E-Plus server is `196.219.103.221`. Verify these audit-time values before testing. Do not store credentials here.

## Test prerequisites

- [ ] Obtain an employee/PIN test session for both POS applications. Admin authentication succeeded, but the separate employee login gate prevented full sales workflow testing.
- [ ] Establish an isolated test destination for posting scenarios involving sales, refunds, stock, and cash. The initial audit submitted no sales or refunds; external writes remain subject to repository rules.

## Confirmed findings

### F1 Keep failed bills immutable and preserve the original submission payload on retry

- [x] Keep failed bills immutable and preserve the original submission payload on retry.

Priority: High. Confirmed through source review and an isolated payload-builder test, not live posting.

Required behavior: Once created, the bill remains locked against business-data edits even if submission fails. Retry must preserve the original submission payload and request identity rather than rebuild business data from current records.

Audit baseline: The backend write guard exempts `rejected` bills, and the response marks them editable. Retry rebuilds their payload through `_branch_current_payload`, whose line reconstruction omits `is_doctor_prescription_product`. That can change a retry payload even without a user edit. The initial audit did not establish that rejected-bill editing was reachable through the UI.

Acceptance: Failed and rejected bills remain immutable in both the UI and backend. Retrying preserves the original header, lines, prescription flags, token, and request revision without creating a corrected revision or duplicate posting. Workflow-managed status and posting identifiers may still update through submission or reconciliation.

Source: callcenter `ab_sales/models/local_bills.py`, `write` (audit line 100), `_branch_result` (audit line 147), `action_retry_branch_submission` (audit line 180), and `_branch_current_payload` (audit line 295).

Resolution verified on 2026-10-13: Rejected submitted bills now remain locked in the backend and POS. Retry reuses the stored wire payload, token, and revision; the payload rebuilder and rejected-bill revision increment were removed. The bill form is read-only and retains Retry. Targeted `ab_sales` upgrade completed on `callcenter19`, and callcenter workers were reloaded.

Validation: Rollback-only Odoo tests passed header and line mutation rejection, prescription-flag preservation, form retry replay, and retry with altered browser data. JavaScript checks passed locked states and direct Retry routing. Authenticated Playwright verified live rejected bill 17608 has zero writable fields, Retry visible, and Add Products hidden. Remote posting was mocked; no external sale or refund was submitted. E3 remains open for the broader end-to-end scenario.

Evidence: [Module changelog](ab_sales/changelog.d/2026-10-13-immutable-failed-bills.md); `/tmp/test_callcenter_f1.py`, `/tmp/test_callcenter_f1_ui.js`, and `/tmp/test_callcenter_f1_browser.js`.

### F2 Restore draft loading when a cached branch is inaccessible

- [ ] Diagnose the offending cached draft and prevent it from blocking all usable drafts.

Priority: High. Reproduced with Playwright on branch POS under the tested admin session.

Observed: Opening POS shows “Draft cache could not be synchronized.” The `pos_load_draft_cache` RPC returns “You cannot access the branch of this draft bill.” Collection validation raises when a cached bill references an inaccessible branch.

Acceptance: Valid drafts remain usable, the affected draft has a clear recovery path, and no business records are deleted or branch restrictions bypassed. Verify admin and authenticated employee sessions.

Source: branch `ab_sales/models/ab_sales_pos_draft_slots.py`, `_draft_authoritative_states` (audit line 137).

### F3 Repair the stale connection health scheduled action

- [ ] Resolve the invalid scheduled action and verify successful scheduled execution.

Priority: Medium. Confirmed in database records and logs.

Observed: Active cron 58, “Branch Connections: Check Health,” calls nonexistent `model._cron_connections('check')`; failure count reached 63. This is stale dev database configuration, not an established clean-install defect.

Acceptance: The invalid call stops, intended health checks are documented and verified, and bill-status polling remains operational. Audit baseline: status cron 21 was active every five minutes with zero recorded cron failures; cron 39 was inactive.

Source: callcenter `ab_sales/models/ab_sales_branch_rpc_config.py`, `action_check_connections` (audit line 340); scheduled action 58 in `callcenter19`.

### F4 Align saved bill notes with the allowed workflow

- [ ] Resolve the mismatch between Save Notes and the submitted-bill write guard.

Priority: Medium. Reproduced with Playwright on saved callcenter sale 24747.

Observed: Save Notes is enabled, but editing notes returns “This bill is locked until its branch submission is resolved. Use Retry.” The bill is already saved.

Acceptance: Decide whether post-submission notes are editable. If supported, persist them through the defined workflow without altering posting identity or status; otherwise disable the action with an accurate explanation. A completed bill should not be directed to Retry merely to edit notes.

Sources: callcenter `ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py`, `bill_wizard_update_notes` (audit line 1486); `ab_sales/models/local_bills.py`, `write` (audit line 100).

### F5 Keep Reset and search results consistent under latency

- [ ] Fix Reset during an in-flight search and verify response ordering on both applications.

Priority: Medium. Reproduced with Playwright by delaying delivery of a real search response.

Reproduction: Search serial 24747, then click Reset before the response arrives. The filter becomes empty, but the list shows one matching bill instead of the unfiltered 724-record audit baseline.

Acceptance: After Reset, results and pagination match the cleared filters. Older responses cannot overwrite newer filter intent. Check both callcenter and branch implementations.

Source: callcenter `ab_sales/static/src/bill_wizard/bill_wizard_action.js`, `loadBills` (audit line 290) and `resetFilters`.

## Configuration and reconciliation follow-up

- [ ] C1 Resolve the original destinations of bills 17605 and 17608. They produced “The branch database changed. Reconcile the original request before retrying.” Verify original posting facts before deciding their next state; do not blindly redirect requests or regenerate tokens.
- [ ] C2 Resolve the missing active connection for `فرع العتبة القاهرة`. Configure the intended destination or document handling of its historical pending bills. Verify its failure does not stop other branches refreshing.

These are observed environment conditions. A successful cron execution does not establish that every branch refreshed successfully.

## Edge cases to validate

These are unverified risks, not additional confirmed bugs. Record and resolve any failure before checking off its scenario.

- [ ] E1 Validate timeout recovery after commit. Drop the response after a sale or return commits, then retry. Expect the original token, exactly one posting, recovered identifiers, and eventual agreement between both systems.
- [ ] E2 Validate duplicate and concurrent submissions. Double-click Submit and retry from two tabs. Expect one posting and a recoverable response for the competing request.
- [ ] E3 Validate failed-bill immutability and exact retry preservation. Attempt to edit header and line business data after creation, including after rejection or an uncertain submission; expect the UI and backend to reject changes. Retry and compare the business payload, prescription flags, token, and request revision with the original stored request. Expect no rebuilt or corrected business payload and no duplicate posting. Covers F1.
- [ ] E4 Validate simultaneous partial returns. Submit overlapping quantities from two sessions, including the final remaining quantity and an over-return attempt. Expect combined posted returns never to exceed the remaining returnable quantity.
- [ ] E5 Validate return units and batches. Exercise alternate units, fractional quantities, multiple batches/prices, and previously returned lines. Expect correct conversion, remaining quantity, refund amount, and stock/cash effects without rounding drift.
- [ ] E6 Validate destination changes with outstanding bills. Change URL or database while requests are pending or unknown. Expect original requests to remain tied to their original destination and require reconciliation before reuse elsewhere.
- [ ] E7 Validate partial outages across roughly 60 branches. Make one and then several branches slow or unavailable. Expect healthy branches to continue refreshing, errors to identify affected branches, and measured duration against an agreed operational target.
- [ ] E8 Validate overlapping cron and manual refresh. Refresh pending, saved, unknown, and rejected records while responses arrive out of order. Expect no status regression, lost identifiers, or duplicate submissions; saved records remain saved.
- [ ] E9 Validate draft synchronization across stale tabs and employee changes. Edit from two tabs, remove a draft in one, reconnect the other, switch employees, and include an inaccessible cached branch. Expect no silent loss, removed-draft resurrection, or one bad draft blocking valid drafts. Covers F2.
- [ ] E10 Validate Bill Wizard response races. Search, Reset, paginate, switch selected bills, and save eligible notes under delayed responses. Expect filters, rows, pagination, details, and notes to remain associated with the correct bill. Covers F4 and F5.

## Regression checks after fixes

These passed during the initial audit; rerun them after related changes.

- [ ] Verify callcenter pagination advances and returns correctly.
- [ ] Verify an unmatched serial shows zero results and clears stale details.
- [ ] Verify branch serial 24746 distinguishes its sale and return documents.
- [ ] Verify Return remains disabled on an existing return document.

## Evidence and completion log

Initial screenshots are temporary local artifacts under `/tmp/odoo-sales-audit-2026-10-13/`: `reset-during-search.png`, `saved-bill-notes-rejected.png`, `branch-return-details.png`, `branch-pos-login.png`, and `callcenter-pos-login.png`. They may contain customer information and may disappear when temporary files are cleaned. Source line numbers and database IDs describe the audit baseline.

For each completed item, record its environment, result, evidence, and relevant commit or configuration change. An implemented change without verification remains open.

| Item | Resolution or test result | Evidence or commit | Verified by | Date |
| --- | --- | --- | --- | --- |
| F1 | Locked failed bills; preserved original request on retry; activated on callcenter19 | Module changelog and focused Odoo, JavaScript, and Playwright checks | Codex | 2026-10-13 |
