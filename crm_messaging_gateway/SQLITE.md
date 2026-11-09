# SQLite queue and optional WhatsApp workspace

This is a development implementation. Existing services/configuration and the original PostgreSQL queue have not been switched. Production cutover, provider sends, webhook activation and production capacity approval are separate actions.

## Runtime and configuration

Install `requirements.lock` into the gateway's own persistent virtual environment. `apsw==3.51.3.0` bundles SQLite 3.51.3; the backend refuses an older runtime. The available `pysqlite3-binary==0.5.4.post2` wheel contains 3.51.1 and is unsuitable. Odoo's interpreter, PostgreSQL database and business operations are unchanged.

Use a single local persistent directory owned by the service user, mode 0700, on an encrypted deployment volume. SQLite itself does not encrypt this database. `encrypted_storage_confirmed=true` is the operator's attestation that the database, WAL, shared-memory files, exports and backups reside on approved encrypted storage. It is not an encryption implementation or automatic verification. Do not use network filesystems, temporary directories or independent copies of the queue for production.

Generic units share `/var/lib/crm-messaging`. The three callcenter units share `/var/lib/crm-messaging-callcenter`. These are alternative deployments; choose the matching directory in the protected configuration:

```json
{
  "database_url": "sqlite:///var/lib/crm-messaging-callcenter/queue.db?busy_timeout_ms=1000&contention_retries=3",
  "encrypted_storage_confirmed": true
}
```

Retain the other Odoo/provider configuration fields. SQLite configurations contain no queue PostgreSQL DSN, role or password. The PostgreSQL implementation remains available through the same `Store` interface. The foreground launcher accepts either backend; `local_setup --encrypted-storage-confirmed` supports preparing a new SQLite configuration in an interactive terminal.

Each operation opens a separate connection, enables foreign keys and `synchronous=FULL`, and uses a short `BEGIN IMMEDIATE` transaction. Claims, fingerprints and receipt creation commit before HTTP. WAL is configured by `app.ops migrate`. Writer acquisition waits for the configured busy timeout and at most the configured contention retries (defaults: 1000 ms, three retries). A per-bot `flock` in the shared queue directory replaces PostgreSQL advisory locking. Lock files are never removed while another process could own their inode. Polling offsets and events, including empty-poll heartbeats, commit atomically.

## Bounded migration

The operator must stop all three messaging services before the final export and keep them stopped through verification and configuration replacement. Do not stop Odoo. Also prevent a separate launcher or legacy sender from running. No export command stops services implicitly.

1. Keep a protected copy of the PostgreSQL configuration and queue. Use that configuration with `python -m app.ops export --file /PRIVATE/queue.jsonl --quiesced`.
2. Prepare the private SQLite directory and a separate protected configuration. Keep sending/reception switches unchanged; changing storage does not authorize provider traffic.
3. With the SQLite configuration, run `python -m app.ops import --file /PRIVATE/queue.jsonl`. The destination must be empty. Import runs in one bounded offline transaction and rolls back on a mismatch.
4. Export the imported queue with `--quiesced` and compare the printed per-table counts and SHA-256 digests with the original export. Import also compares the digest of every inserted row before committing. Inspect `python -m app.ops status` and `review`.
5. Only after the production approval and storage/capacity gates, install the reviewed units and start the three messaging services against the same SQLite file. Existing independently installed units may need a reviewed manual replacement: the installer deliberately refuses unknown differing definitions.

Exports are private JSON Lines, limited to 512 MiB and one million rows, and stream one row at a time. They preserve event/operation IDs, fingerprints, operation UUIDs, attempts, offsets, timestamps, leases, receipts, provider outcomes and operator audit records. No pruning runs. Interrupted outgoing `sending` rows remain `sending`; expired sending leases become uncertain review reports, never ordinary pending jobs. Incoming leases retain the original recovery behavior.

Before SQLite processes traffic, rollback may use the untouched PostgreSQL queue after verifying that neither queue advanced. **After SQLite processes any traffic, do not restart the old PostgreSQL configuration.** Reconcile offsets, receipts, provider IDs, reports and uncertain sends first. This release intentionally supplies no automatic reverse migration or uncertain-send reset.

## Backup and recovery

Install and explicitly enable the matching `crm-messaging[-callcenter]-backup.service` and `.timer` after cutover approval. The timer runs hourly; `app.backup` writes a unique private snapshot under the queue directory's `backups/`, uses SQLite's online backup API, checks integrity, and flushes the backup and its directory. The operation has a 60-second deadline and cleans up an incomplete destination. No automatic retention or pruning is enabled initially.

A manual snapshot is `python -m app.ops backup --file /PRIVATE/backup.db`. Never copy only an active `.db` while omitting its WAL. For a restore drill, stop the messaging consumers, preserve the damaged/current queue and its sidecars, restore a snapshot to a new private path, verify integrity/counts/digests and inspect `review`, then configure that new path. If the snapshot predates provider traffic, reconcile it against Odoo and provider evidence before starting dispatch. An old snapshot may otherwise resend previously accepted operations. Automated tests reopen the backup as a separate store and verify all records and uncertain-send blocking.

## Monitoring and capacity gate

`app.ops status` exposes counts by account/state, oldest outstanding age, uncertain-send count, polling heartbeat age, database/WAL bytes and free disk space without message bodies. `crm_messaging.metrics` logs gateway/Odoo HTTP latency, provider dispatch duration and polling event lag. Writer contention logs include bounded attempt counts. Alert on growing backlog/age, uncertain sends, missing polling heartbeats, sustained latency/contention, WAL growth and insufficient free space for queue plus backups. Empty polls update the heartbeat; event lag is emitted only when an incoming event exists.

`python -m app.benchmark --directory /PRIVATE/validation --peak-events-per-second MEASURED_PEAK --seconds 60 --processes 4` creates a new synthetic queue, schedules twice the supplied rate, runs incoming and outgoing lifecycles across independent processes, verifies completion and reports elapsed throughput and p95 cycle latency. It never uses the configured live queue or provider APIs. A reference peak must come from representative measured production traffic. The existing 14 incoming / 11 outgoing rows are not a production load baseline. Synthetic validation numbers and any missed target are recorded in `SQLITE_VALIDATION.md`; they do not approve capacity.

## WhatsApp

See `../ab_crm_whatsapp_workspace/README.md`. Outgoing-only accounts may omit webhook credentials and verification tokens while `reception="disabled"` (the WhatsApp default). Activating reception requires explicit `reception="webhook"`, app-secret signature verification, a verification token, and the Odoo account's separate signed-reception flag. Existing Telegram defaults and polling remain compatible.

References: [SQLite WAL-reset fix](https://sqlite.org/wal.html#walreset), [APSW connections](https://rogerbinns.github.io/apsw/connection.html), [online backup API](https://rogerbinns.github.io/apsw/backup.html).
