# Media, reactions and voice validation — 2026-11-05

**82 tests passed, zero skips**, with provider HTTP mocked and the existing isolated PostgreSQL queue. Reproduction:

```bash
PATH=/tmp/chatter-ffmpeg/usr/bin:$PATH MESSAGING_TEST_DSN_FILE=/tmp/crm_messaging_test_dsn /tmp/crm_gateway_venv/bin/python -m pytest tests -q
```

New checks cover profile/quote/media normalization, reaction acceptance evidence, multipart document sending, fixed-origin bounded downloads, metadata persistence before transfer, actual Ogg/Opus conversion, rejection of a 301-second recording even with a false declared duration, local rejection without provider submission, and failed-download evidence. Existing outage, polling, ordering, replay, lease, recovery and uncertain-send checks remain passing. FFmpeg 6.1.1 was extracted from the distro package under `/tmp` for validation; install the OS package on the worker host before audio/voice activation. The live contact/reply pilot remains separately gated and was not performed.

See [workspace validation](../ab_crm_sales_workspace/VALIDATION.md) for Odoo, browser, translation and rollout evidence. No live gateway configuration, provider credentials or running services were changed.

---

# Independent FastAPI and live reception — 2026-11-04

Real Telegram reception was verified on `callcenter`: six distinct provider updates produced six incoming Odoo messages and six ledger entries in one conversation. Two messages contained the requested test marker and had different Telegram message identities. Replaying one event returned its existing Odoo message rather than creating a duplicate. Telegram reported zero remaining pending updates. Sending stayed disabled and the outgoing queue remained empty.

A controlled stop of the task-owned API child exercised the previous supervisor's restart policy. Systemd restarted all three gateway processes, preserving offset `549604502` and all six completed events. The captured hashes of 11 sales/order/inventory tables remained unchanged, including 116,240 inventory rows. Neither user-managed Odoo process was stopped. Visible staff notification and claiming still require user confirmation because browser access failed.

The user subsequently required FastAPI to have no runtime dependency on Odoo. The implementation now provides independent API, receiver and worker units. FastAPI loads only local configuration, `/health` has no external dependency, and `/ready` checks only the queue. The receiving worker starts without fetching provider tokens when sending is disabled. Odoo transport/server outages defer incoming queue records without exhausting validation attempts; lease checks prevent stale acknowledgements.

- **74 tests passed** with the isolated PostgreSQL test queue; provider HTTP remained mocked in that suite.
- A real temporary FastAPI process started with deliberately unreachable Odoo and PostgreSQL test endpoints. `/health` returned 200, `/ready` and webhook intake returned 503, and the process stayed alive. The temporary process was stopped and its port released.
- All three independent system units passed `systemd-analyze verify`, shell syntax and isolated boot-enablement checks. They have no mutual `Requires`, `BindsTo` or `PartOf` links.
- Earlier startup logs showed HTTP 409 credential responses. Four bounded read-only credential retries and retryable receiver initialization were added; six concurrent real credential fetches subsequently passed without exposing tokens.

**The independent-unit migration is installed and verified.** The user ran the installer at 20:22 Cairo time. All three installed units match their repository definitions and report `active/running` and `enabled`, with zero restarts since migration. The API runs directly under Uvicorn on `127.0.0.1:5088`, without Odoo, receiver or worker dependency links; `/health` and `/ready` both return 200. The previous combined supervisor was stopped and replaced without touching Odoo or changing reception/sending flags.

After migration, seven distinct Telegram updates are completed in the queue and correspond to seven unique Odoo messages and seven ledger entries. The durable next offset is `549604503`; the outgoing queue remains empty and sending is disabled. The staff conversation is still unclaimed, and visible notification/claim plus the separately approved contact-sharing/reply pilot remain outstanding. No actual machine reboot was performed. Operational start/status/stop commands are in `DEVELOPMENT.md`.

---

# Previous combined callcenter service — 2026-11-04

The previous foreground launcher did not provide reboot persistence. A callcenter-specific system service and an installer now enable boot startup without starting or activating reception. The service supervises one FastAPI process, one receiver and one worker under the existing unprivileged account.

- Gateway suite: **61 passed**, with the isolated PostgreSQL test queue and mocked provider requests.
- Service unit verification and installer shell syntax passed. Boot-target enablement was verified in an isolated temporary systemd root.
- Two temporary user services verified the installed systemd restart policy: exit 75 restarted once; exit 78 did not restart. Both test services were stopped afterward.
- Regression checks cover disabled reception before network access, process ownership across boots, cleanup after each child failure, and separate handling of receiver safety exits versus API/worker failures.
- Actual launcher `serve` returned exit 78 for the disabled account without starting reception.

The user ran the installer, and the installed unit was verified to match the repository definition. The unit is **enabled** for boot, with `Restart=on-failure` and `RestartPreventExitStatus=78`. The user then explicitly approved reception. The existing `tg-callcenter` Odoo account was enabled through the ORM after confirming no old worker or approved legacy replies; its company, replica 102 and stores 29/140 were preserved. Protected gateway reception was enabled atomically with mode 0600, while outgoing sending stayed disabled. Startup preflight passed. A private hashed baseline of sales, orders and inventory was captured before activation.

The initial noninteractive start was denied by the operating system; the user later started the service locally and live reception/restart verification passed as recorded above. Odoo remains PyCharm-managed. The dedicated API key expires on 2026-11-11 at 12:48:59 UTC. See `DEVELOPMENT.md` for the replacement independent services and renewal requirements.

---

# Odoo-managed Telegram credentials — 2026-11-04

The gateway suite passes 56 tests with the isolated PostgreSQL test DSN, including Odoo token loading, provider identity matching, secret redaction and rejection of duplicated literal tokens in Odoo-managed configuration. Existing controller-v1, polling, competing receiver, durable offset, ordering, restart and uncertain-send checks remain included. All provider HTTP is mocked. Real account-bound credential HTTP and browser setup evidence is in `../ab_crm_sales_workspace/VALIDATION.md`.

The real Telegram pilot is not live. See `DEVELOPMENT.md` for Odoo system-parameter setup and the remaining queue, reload, participant and approval steps.

---

# Polling/controller validation — 2026-11-04

The final gateway suite passes **55 tests**, with no skips, against the isolated PostgreSQL test queue. All Telegram/WhatsApp HTTP calls are mocked. Real Odoo controller authentication and messaging regressions pass **23 tests**; the workspace/controller clean install and upgrade pass **20 tests**. English/Arabic browser checks passed.

**The real Telegram pilot remains unperformed.** Local bot-token entry, queue-role provisioning, the user-managed Odoo reload, a participant and explicit activation approval are still required. See [current evidence](../ab_crm_sales_workspace/VALIDATION.md) and [the development runbook](DEVELOPMENT.md). Earlier webhook-only evidence is retained below.

---

# Validation — 2026-11-03

Implementation was validated in isolated local databases. The user's callcenter/POS processes were not stopped or restarted. Public webhooks, production accounts and real provider sends were not activated.

| Check | Result |
|---|---|
| Fresh Odoo install of `ab_crm_whatsapp,ab_crm_telegram` with shared dependency | Passed on `crm_messaging_fresh_20261103` |
| Targeted upgrade of all three new addons | Passed on `crm_messaging_validation_20261103` |
| Odoo business/security suite | **20 passed, 0 failures, 0 errors** on fresh install and final upgrade |
| FastAPI/provider/PostgreSQL suite | **29 passed, 0 skipped** |
| Real JSON-2 HTTP against isolated Odoo | Incoming text, identical replay, conflicting replay rejection, wrong-account rejection, missing bearer rejection, direct CRM ORM denial, outgoing snapshot, exclusive lease, durable receipt replay, fresh send authorization, acceptance evidence replay passed |
| Translations | 112 extracted terms in each language across the three addons; all translated in `ar.po` and `ar_001.po`; `msgfmt --check-format` passed for all six catalogs |
| Runtime language | English and Arabic action/form labels verified; Arabic server-side review guard verified |
| Browser | Arabic delivery list/form rendered; computed direction `rtl`, no horizontal overflow; provider acceptance and approval actor/time visible |
| Static/package | Python parsing, XML parsing, manifests/dependency files, module ownership, developer/author metadata and pinned dependency consistency passed |
| Production archive | Includes only new addons and the new service; excludes tests, caches, dev requirements and protected configuration |
| Cleanup | Temporary API key revoked, test logins archived, agent-created browser tab closed, temporary Odoo stopped; ports 5069/5072/5088 released |

The Odoo runner's statistics line includes setup/teardown accounting (`22 tests`), while the actual result summary reports **20 test methods**. The number above uses the result summary.

Gateway tests use a separate `crm_messaging_queue_test_20261103` database and mock every provider request. They cover signed raw webhook bytes, Telegram secret verification, account mismatches, unsupported attachments without downloads, content fingerprints, body limits, duplicate/conflicting events, concurrent workers, lease/crash recovery, acknowledgment crash recovery, rate limits, bounded retries, ambiguous sends and send authorization.

Odoo tests cover branch/company isolation, a foreign service user, accidental service/manager group combinations, direct ORM restrictions, context-based approval spoofing, atomic approval, immutable snapshots, WhatsApp expiry, out-of-order states, receipt idempotency, safe retries, review-note protection, disabled/archived accounts and evidence reporting after archival.

## Reproduction

Runtime source: `/opt/odoo19/worktrees/callcenter19`. Odoo interpreter: `/opt/odoo19/venv19/bin/python`. Runtime addons were verified as `/opt/odoo19/server/addons,/opt/odoo19/worktrees/callcenter19`. Production config was read to identify runtime paths; database writes were restricted to the named isolated validation databases.

Odoo commands used the private validation config `/tmp/crm_messaging_validation.conf`, `--http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0 --stop-after-init --no-http`, and `--test-tags=/ab_crm_messaging`. Odoo's test runner can still reserve the HTTP port even with `--no-http`; the separate temporary HTTP server was stopped before the final test runs. No existing user process was terminated.

- Fresh install: `-d crm_messaging_fresh_20261103 -i ab_crm_whatsapp,ab_crm_telegram`.
- Final upgrade: `-d crm_messaging_validation_20261103 -u ab_crm_messaging,ab_crm_whatsapp,ab_crm_telegram`.
- Gateway: `MESSAGING_TEST_DSN_FILE=/tmp/crm_messaging_test_dsn /tmp/crm_gateway_venv/bin/python -m pytest tests -q` from `crm_messaging_gateway`.
- Dependency consistency: `pip check` reported no broken requirements. Runtime versions are recorded in `requirements.lock`; the formatter was a temporary development tool and is not a runtime dependency.

Local evidence logs:

- `/tmp/crm_messaging_fresh.log`
- `/tmp/crm_messaging_final_tests3.log`
- `/tmp/crm_messaging_http.log`
- `/tmp/crm_messaging_final_language.log`

## Known limits and activation prerequisites

- The isolated login page logged a shared `web.assets_frontend` compilation error, `Undefined variable: "$black"`. The backend messaging screens rendered correctly. These addons declare no shared assets, and no shared frontend files were changed. Investigate the deployment's existing web asset baseline before rollout.
- The gateway test client emits a Starlette deprecation warning about its HTTPX adapter. Tests pass; this affects test tooling, not the worker's HTTP calls.
- Meta's developer send/webhook pages returned HTTP 429. The current official [WhatsApp Business Messaging Policy](https://business.whatsapp.com/policy) was accessible and confirms the 24-hour reply rule. Provider credentials, app/API-version provisioning and actual callbacks still require an authorized live pilot.
- No live WhatsApp number or Telegram bot was registered or contacted. HTTPS hostname/certificate, provider identifiers, secrets, branch mappings and explicit activation authorization remain deployment inputs. Follow the README's one-number/one-bot pilot checklist before enabling production traffic.
