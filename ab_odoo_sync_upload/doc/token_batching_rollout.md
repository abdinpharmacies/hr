# POS branch tokens and batching — 19.0.1.7.0

This version is based on the POS sender, including its Cloudflare User-Agent,
queue ownership, persisted receipts, failure states, and dependent-job safeguards.
Use the `pos19` commit; do not replace this addon with the reports19 sender package.

## Behavior

The sender exchanges its existing API key and hardware identity at
`/ab_odoo_sync/token`, then sends `Authorization: Bearer ...` to the unchanged
upload/health endpoints. Tokens are reused across workers in a restricted database
record. The receiver controls expiry (normally 15 minutes). One expired/unknown
token refresh is allowed per request; revoked tokens and other HTTP 403 failures
require corrective action rather than repeated key authentication.

Both token issuance and uploads send `User-Agent: AB-Odoo-Sync/19.0`.
Authorization headers are never forwarded through redirects. The branch database
contains its raw client token, like the existing long-term API-key parameter;
protect its backups and administrator access accordingly.

The first event schedules a fixed deadline. Later events join the pending batch
without moving that deadline. Execution claims eligible, unowned records up to
the configured batch size. Each branch database performs only one upload at a
time, across channels. Historical uploads yield while live updates are pending.
Queue congestion and HTTP/receiver processing can extend delivery beyond the
batching delay.

Failed records retain their owning job, and manual Retry reuses that job. Receipts
and failure metadata commit in the existing separate delivery transaction, so
queue rollback does not lose acknowledgements. A retry sends only remaining
eligible records; pending continuations handle additional unowned events even if
an earlier batch failed. Existing explicit-ID and no-argument jobs remain valid.

Transient transport errors retry with jittered delays starting at five seconds,
increasing to a five-minute cap. A longer valid Retry-After is honored. Permanent
failures and partial/malformed acknowledgements retain the POS failed-job behavior.
The controller safeguard still holds dependent jobs until delivery succeeds.

## Branch System Parameters

| Key | Default | Behavior |
|---|---|---|
| `ab_odoo_sync.use_branch_tokens` | `True` | Enable token exchange and reuse. |
| `ab_odoo_sync.upload_batch_delay_seconds` | `5` | Integer 0–300. Zero disables intentional waiting; invalid values use five seconds. |
| `ab_odoo_sync.batch_size` | Existing value | Existing batch-size validation remains unchanged. |

Settings use Odoo's existing parameter cache and normal committed-change
invalidation. New delay settings affect new jobs, not already scheduled deadlines.
Existing API key, report URL/database, and hardware discovery are retained.

## Pilot deployment

1. Back up the branch database and compare any local addon modifications.
2. Stop its Odoo and queue services **before** updating the source. Upgrade only
   `ab_odoo_sync_upload` to `19.0.1.7.0` using that branch's config and database,
   with `--workers=0 --max-cron-threads=0 --no-http --stop-after-init`.
3. Restart the branch services. Enable the existing **AB Odoo Sync: Branch Upload**
   scheduled action in Odoo. Its recovery sweep handles scheduling races; existing
   installations retain their previous active flag because the record is noupdate.
   Fresh installations enable it by default.
4. Run the connection test. Confirm report logs show `auth mode=token`, branch
   outbox records become Sent, and queue jobs complete successfully.
5. Retry prior authorization failures after verifying the branch's key and
   hardware configuration. Inspect partial/business rejections separately.
6. Monitor `AB sync send` logs for batch size, HTTP duration, and oldest live-event
   age. Roll out progressively after the first branch passes.

The report receiver must already support branch tokens. Legacy authentication is
currently disabled on the report server; upgraded branches can still obtain tokens.

## Rollback

Setting the batching delay to zero removes intentional delay for new jobs.
Setting `ab_odoo_sync.use_branch_tokens=False` restores legacy headers, but only
works if the report administrator deliberately enables legacy authentication too.
Do not discard outbox events, reset event UUIDs/revisions, or delete pending jobs.
Rolling back code requires stopping services first; the additional token table may
remain in the database.
