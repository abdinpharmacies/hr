# Dual-channel source validation — 9 November 2026

Validated checkout: `/opt/odoo19/worktrees/callcenter19`, branch `callcenter19`. Live configuration maps this checkout to `callcenter`; all installation/test writes used isolated databases. Existing composer/UI work and AGENTS.md changes were preserved. `ab_whatsapp_api` source is unchanged.

## Passed checks

| Check | Fresh result |
|---|---|
| Gateway regression suite, real isolated PostgreSQL queue | 171 passed; 1 skipped because FFmpeg/FFprobe are unavailable |
| Targeted workspace + WhatsApp upgrade | 112 selected Odoo tests, 0 failures/errors |
| Core messaging upgrade in its own fixture environment | 30 selected Odoo tests, 0 failures/errors |
| Companion fresh install | 24 selected Odoo tests, 0 failures/errors; subsequent access, polling-cursor and mobile additions covered by final upgrade suite |
| Desktop HOOT suite | 56 tests, 338 assertions |
| Mobile WhatsApp HOOT suite | 7 tests, 27 assertions; includes LTR/RTL grouping and separate drafts |
| Syntax | 75 Python files and 23 XML files parsed |
| Arabic catalogs | All 6 changed catalogs pass `msgfmt --check-format`; exported terms have no missing translations |
| Runtime languages | Account/provenance labels verified under `en_US`, `ar`, `ar_001`; Arabic frontend provenance label and RTL metadata checked |
| Dependencies | Pinned isolated gateway environment passes `pip check`; production Odoo dependencies untouched |
| PostgreSQL recovery | Synthetic queue custom-format backup restored into a disposable PostgreSQL database; all four queue-table counts/digests matched, review state and dispatch evidence retained |
| Source/package hygiene | `git diff --check`; runtime archive excludes tests, test assets, caches, private configs and secrets |

Odoo result counts use the runner's final selected-test summary; its per-module statistics also include setup/teardown operations and must not be added as distinct tests. Desktop suites overlap: the combined WhatsApp suite includes the workspace suite. Mobile tests repeat relevant scenarios under the mobile preset.

## Reproducible environment and evidence

- Gateway interpreter: `/tmp/callcenter-dual-test-venv/bin/python`; installed from `crm_messaging_gateway/requirements-dev.txt`.
- Odoo browser interpreter: `/tmp/callcenter-odoo-test-venv/bin/python`; references the existing Odoo runtime packages read-only and adds pinned `websocket-client==1.8.0` separately.
- Neutral Odoo config: `/tmp/callcenter-dual-test.conf`; isolated filestore: `/tmp/callcenter-dual-data`. Credentials are not included in this report or runtime package.
- Odoo DBs: `callcenter_dual_test_20261109`, `callcenter_dual_core_test_20261109`, `callcenter_dual_fresh_test_20261109`.
- Queue DB: `crm_gateway_dual_test_20261109`; recovery test creates/removes only its own uniquely named scratch restore database.
- Ports: 5069/5072 for workspace; 5073/5074 for independent core/fresh checks. All Odoo runs use workers=0, cron threads=0 and stop-after-init. Temporary servers exited; validation ports were checked after completion.
- Final logs: `/tmp/callcenter-dual-final-acceptance.log`, `/tmp/callcenter-dual-core-verified.log`, `/tmp/callcenter-dual-fresh.log`, `/tmp/callcenter-dual-languages.log`.
- Runtime package: `/tmp/callcenter-dual-channel-runtime-20261109.tar.gz`; includes the three changed addons and gateway runtime. Source tests remain in the checkout.

Final upgrade command uses `-u ab_crm_sales_workspace,ab_crm_whatsapp_workspace --test-tags /ab_crm_whatsapp_workspace,/ab_crm_sales_workspace`; the preceding targeted upgrade also updates `ab_crm_messaging`. Core checks use `-u ab_crm_messaging --test-tags /ab_crm_messaging` in the separate core database. Fresh checks use `-i ab_crm_whatsapp_workspace --test-tags /ab_crm_whatsapp_workspace`. No `-u base` was run.

## Acceptance covered

Tests exercise legacy HTTP 410 and direct-RPC denial; queue-only sends; account/key/signature routing; independent send controls; opaque identity quarantine; import cursors, skipped/conflicting records and reruns; chronology independent of live polling cursor; no historical alerts/window/queue; manager linking, stale/conflicting previews and audit; unauthorized staff/service/company/session access; grouped pagination; cross-stream order origin; approved templates, dispatch revocation and expiry; delivery replay/reordering; PostgreSQL concurrent leasing and uncertain outcomes; separate drafts/attachments/quotes; desktop/mobile composition and RTL.

Initial failures were corrected: new send-switch fixtures, a missing canonical contact fixture, a translation-helper collision from a local variable named `cursor`, and browser test harness assumptions. Core messaging fixtures were moved to their own isolated module environment instead of weakening workspace mapping validation. Final review additionally found and fixed a live-poll cursor issue when historical records display in timestamp order rather than insertion order.

## Deployment gates still pending

No live Odoo upgrade/restart, provider call, host credential change, tunnel configuration, customer association, history import or customer message was performed. The six outgoing messages and one phone-match candidate remain deployment-review inputs from the diagnosis, not newly modified/verified records.

Domain, protected Meta configuration and app/account compatibility with Graph v26.0 must be verified before reception. Named pilot sending requires explicit approval. Inbound media, reply/profile/contact normalization, reactions and additional opaque identity formats remain the separately tested increments after the bounded text/location/status pilot. Outgoing media/reactions default off; the FFmpeg skip is not evidence that voice delivery works on this host.

The restore drill proves the PostgreSQL implementation against synthetic isolated data. Actual production backup scheduling, live queue reconciliation, provider end-to-end evidence and production recovery remain rollout checks in [the runbook](omnichannel-callcenter-runbook.md). No full end-to-end live Meta or production-capacity result is claimed.

## Follow-up: template preference language

Saved replies and approved WhatsApp sending pickers now filter by the user's preference language. Existing EN/AR-tagged saved replies remain compatible without a backfill; new saved replies store their language. Arabic regional variants match Arabic. Four targeted language, save/edit, authorization and template-eligibility tests passed after upgrading the two owning modules on the isolated workspace database (`/tmp/callcenter-template-language.log`). The added Language field label is translated in both Arabic catalogs. This follow-up does not change the earlier full-suite counts into a claim of a new full-suite run.
