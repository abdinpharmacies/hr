# Supplier Claim Dynamic Workflow Validation

Validated on 2026-11-17 against the local Odoo 19 runtime and PostgreSQL using
an isolated database (`codex_claim_workflow_20261117`).

## Results

- Targeted module installation and 19.0.7.2.0 schema upgrade passed.
- Focused post-install suite: 27 tests, 0 failures, 0 errors.
- Includes browser regression checks for incomplete draft creation and existing workflow views.
- Separate Playwright verification covers actual draft creation/submission, archived supplier
  contact defaults, explicit confirmation, month/year saving, and optional attachment controls.
- Responsive checks at 1440, 1024, 800 and 390 pixels found no page/timeline horizontal
  overflow; entry groups remain parallel at medium sizes and stack on mobile; header actions
  occupy one line. A 13-stage workflow includes parallel and long-named stages.
- Participant dedicated uploads and additional Chatter uploads passed browser verification.
- Concurrent upload check: one upload saved, the competing request blocked, one document recorded.
- Business/security tests cover historical approver visibility, removal of decision/edit rights,
  immediate allowed-field revocation, returned corrections, company isolation, attachment
  replacement/rename/deletion and token-route protections.
- Manual tax/net entry and the non-blocking discount-conditional mismatch warning are covered.
- Python compilation and `git diff --check` passed.

## Upgrade checks

Existing business-table row counts and fingerprints are captured before/after upgrades.
The intentionally removed tax-rate field and newly introduced month/contact-confirmation
fields are excluded from the content comparison. Existing tax/net entries are preserved.
Historical stage visibility is backfilled from current configured approvers and recorded
stage decision actors; existing decisions and documents are not rewritten.

Do not run fixture-based module tests against a live database. Use a targeted module upgrade
and read-only health/view/data checks there. Telegram remains outside this release.

## Development deployment

`hr_db_dev` was upgraded to 19.0.7.2.0 and the server on port 8066 restarted.
Before/after business fingerprints match for 478 claims, 2 workflows, 7 configured
stages, 1,585 runtime stages, 1,546 history entries and 481 documents, including
unchanged approver and allowed-field links. The membership backfill produced
9,276 historical stage-user links. Read-only model/view checks and HTTP health passed.

Existing incomplete legacy history/document rows cause not-null constraint
warnings during the upgrade; those business records were preserved unchanged.

## Remote deployment

`hr_db` on `abdinctrl` was upgraded to 19.0.7.2.0 and `odoo19s1.service`
restarted successfully. Read-only live model/view checks passed. Before/after
fingerprints preserve 478 claims, 3 workflows, 13 configured stages, 1,585 runtime
stages, 1,483 history entries and 457 documents, with unchanged approver links.
One allowed-field link was removed because it referenced the explicitly removed
Tax Discount Rate field; backup relation/field metadata confirmed that it was the
only relationship change. The membership backfill produced 9,276 links.

The first remote attempt was rolled back after a service-account working-directory
permission error. Retrying from `/opt/odoo19s1` succeeded. The original source and
full database backups are under `/opt/odoo19s1/backups/claim-workflow-20261117/`.
The development backup is under `/opt/odoo19/backups/claim-workflow-20261117/`.

## 19.0.7.2.1 date and form patch

- Isolated module suite: 28 tests, 0 failures, 0 errors.
- Browser checks passed ISO typing, leap-day input, standard calendar selection,
  saving/reloading a non-first-day date, read-only ISO output, Name/Phone labels,
  field order and responsive rendering at desktop, medium and mobile sizes.
- An independent standard date input retained its US-language format (11/17/2026),
  confirming that language settings and other date widgets were not changed.
- Browser evidence: `/opt/playwright/artifacts/hr/claim-date-20261117/`.
- Remote deployment and upgrade are manual at the user's request; this patch
  does not change files or services on abdinctrl.

Local `hr_db_dev` was upgraded to 19.0.7.2.1, with unchanged fingerprints across
all existing business-table columns, including Claim Month. The 479 existing
claims and their dates were preserved. The local server restarted on port 8066;
HTTP and read-only model/view/version checks passed. No remote action was taken.

## 19.0.7.2.2 header and arrow patch

- Existing module suite: 28 tests, 0 failures, 0 errors.
- Browser verification passed 24 layout cases across LTR/RTL, widths 1440/1024/800/390,
  and short, long and parallel approval assignments.
- Confirmed actions are in the native button area without statusbar overlap; compact
  menus remain accessible. Draft Submit and returned Resubmit visibility passed.
- No visible Step labels; arrows follow direction and sit on the incoming side of
  each sequence group, attached during wrapping. No page/timeline horizontal overflow.
- The sticky amount warning remains below the header on scroll.
- Evidence: `/opt/playwright/artifacts/hr/claim-header-20261117/`.
- Local upgrade preserves all business fingerprints (480 claims, 1,595 runtime stages,
  1,552 history rows and 481 documents, plus workflow configuration and links).
- Remote files and services are unchanged; deployment/upgrade remains manual.
