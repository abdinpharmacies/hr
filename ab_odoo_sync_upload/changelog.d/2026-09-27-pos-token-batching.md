# POS branch tokens and configurable batching

## Recent relevant commits

- `3140ac3a126d2a233e51e9a5410f1f463650b3f4` — emadco88 — 2026-09-25
  Original subject: `ab_odoo_sync_upload/ FIX fake queu_job done`
  Preserve delivery ownership, separately committed receipts/attempts, honest queue
  failure states, manual retry behavior, and the dependent-job controller safeguard.
- `390db7fa1d233de540f50269fabba550ad911c51` — emadco88 — 2026-09-25
  Original subject: `ab_odoo_sync_upload/ FIX User-Agent cloudflare issue`
  Preserve `AB-Odoo-Sync/19.0` on all report requests.
- `ae95657e3c8c2df8487b9955f35c13e5ec7da74d` — emadco88-report-server — 2026-09-27
  Original subject: `ab_odoo_sync_upload/ FIX expensive api auth`
  Adapt its token and batching behavior to the POS delivery implementation.

Inspected these changes and the current module diff before preparing this entry.

## Current changes before commit:

- Add restricted shared client-token storage, coordinated refresh, expiry handling,
  explicit legacy fallback setting, and credential-safe transport errors.
- Configure batching with the built-in cached system parameter, default five seconds.
- Coalesce channel jobs with fixed deadlines; claim outbox rows at delivery time,
  respect existing ownership, and continue after bounded batches.
- Serialize uploads across branch workers and channels; prioritize live updates.
- Preserve existing queued arguments, partial receipts, manual retries, and durable
  attempt/error metadata. Token-refresh contention postpones without marking failure.
- Use five-second-to-five-minute jittered retry backoff and retain validated Retry-After.
- Keep the existing recovery cron's upgrade state; enable it on fresh installations.
- Add timing/age logs, Arabic translations, rollout notes, and version 19.0.1.7.0.

## Validation

- Upgrade from the original POS 19.0.1.6.0 and fresh 19.0.1.7.0 installation passed.
- Eighteen delivery checks passed through the actual queue controller: pre-upgrade
  jobs, cached settings, fixed deadlines, zero delay, continuations, persisted partial
  receipts, manual retries, transient/permanent failures, malformed acknowledgements,
  cross-worker locks, live priority, ownership, interrupted workers, dependencies,
  exact job arguments, token ACL/cache contention, and Retry-After validation.
- Real HTTP token issuance/reuse and expiry refresh passed against an isolated report
  receiver. Revocation does not trigger key reauthentication. User-Agent, redirect
  prevention, HTTP classifications, malformed error codes, certificate failure, timeout,
  redacted errors, and explicit legacy mode passed transport checks.
- The actual POS HTTP queue endpoint postponed a busy sender without a closed-cursor
  error and then successfully uploaded to the isolated receiver using a token.
- Exported POT; both Arabic PO files passed msgfmt --check-format. Arabic token field
  and configuration action verified at runtime. Python/XML and git diff checks passed.
- Development scripts/logs remain outside runtime addons at
  `/opt/odoo19/validation/pos_sync_tokens`. No production database/service changes.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/models/__init__.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_client_token.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_transport.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/data/crons.xml`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/security/ir.model.access.csv`
- `ab_odoo_sync_upload/views/configuration_views.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/doc/token_batching_rollout.md`
- `ab_odoo_sync_upload/changelog.d/2026-09-27-pos-token-batching.md`
