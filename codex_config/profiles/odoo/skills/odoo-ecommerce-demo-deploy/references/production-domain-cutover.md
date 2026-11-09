# Production domain cutover and rollback

Use only for promoting the existing ecommerce service to `abdinpharmacies.com`
and reversing that routing. Keep Odoo 19 on its existing ports and keep its
existing database and filestore. This is not an Odoo-version database migration.
An explanation or skill-edit request does not authorize live changes.

## Recorded baseline and limits

Read-only inspection of the server's Nginx files on 2026-11-04 observed:

| Domain | File | HTTP upstream | Realtime upstream | Realtime location |
| --- | --- | --- | --- | --- |
| `abdinpharmacies.com` | `/etc/nginx/conf.d/odoo15.conf` | `odoo` at `127.0.0.1:9150` | `odoochat` at `127.0.0.1:4053` | `/longpolling` |
| `store.abdinpharmacies.com` | `/etc/nginx/conf.d/odoo19.conf` | `odoo19` at `127.0.0.1:7090` | `odoochat19` at `127.0.0.1:7093` | `/longpolling` |

Both files contain HTTPS listeners and certificates under
`/etc/letsencrypt/live/abdinpharmacies.com`. File inspection does not establish
which config the running workers loaded, certificate validity, backend versions,
or database selection. The `odoo15.conf` filename alone is not version evidence.
The [deployment environment](deployment-environment.md) records Odoo 19 database
`ecom19`, service `odoo19.service`, and its matching filestore. Recheck them.
No cutover or rollback was executed when this reference was written. There is no
saved operational backup or completed cutover record yet. Do not invent either.

The intended change is:

```text
abdinpharmacies.com: 9150 -> 7090
Odoo 19 WebSocket: /websocket -> 7093
store.abdinpharmacies.com: remains on 7090 unless separately agreed
```

The main domain will stop exposing its former backend. Existing data in that
backend is not merged into `ecom19`. The old login URL's action, record, company,
and menu IDs are database-specific; start with `/web/login` and navigate normally.

## Preflight and recovery record

1. Connect with `ssh ecommerce`. Inspect effective Nginx includes (`nginx -T`),
   domain blocks, upstream consumers, DNS/proxy path, TLS, active service commands,
   listening ports, and HTTP responses. Keep full config output private. Confirm
   that only the intended main-domain block consumes any upstream being edited;
   otherwise use a dedicated upstream instead of changing shared routing.
2. Verify the Odoo 19 service actually serves `ecom19` and selects it under Host
   `abdinpharmacies.com`. Check `db_name`, `dbfilter`, `proxy_mode`, workers and
   the gevent listener. Stop if the main hostname selects another database or
   exposes database selection. A port change does not fix database filtering.
3. Confirm the old backend is healthy and can remain available for rollback.
   Capture its public login behavior before switching. Coordinate the switch
   with active staff so requests do not continue in an unintended backend.
4. Before editing, create a unique root-only cutover directory outside Nginx's
   included directories, for example `/opt/odoo19/backups/domain-cutover-<UTC>`.
   Preserve every file to be changed with ownership/mode, record SHA-256 checksums,
   and save a private effective-config snapshot. Never put backup `.conf` files
   in `conf.d` or `sites-enabled`.
5. Save a durable recovery record in that directory: timestamp, exact backup
   paths, before/after hashes and scoped diff, service/database mapping, original
   website domain, and both existence and value of `web.base.url` and
   `web.base.url.freeze`. Identify the website unambiguously; use a stable XML ID
   when available, never a guessed database row ID. Record any extra modified
   config or external callback setting and its previous value.
6. Retain a verified database backup and matching filestore for disaster recovery,
   using the environment reference's backup procedure and a consistent backup
   method. These backups are not the normal routing rollback mechanism.
7. Keep `store` on the same backend by default. State that it will then be another
   address for live production data, not an isolated test environment. Redirecting
   or restricting `store` is a separate explicit decision; capture its prior
   behavior and config if included in the authorized change.

## Apply the authorized cutover

1. Make the smallest main-domain config change. With the recorded baseline and
   exclusive upstream ownership verified, edit `/etc/nginx/conf.d/odoo15.conf`:

   ```nginx
   upstream odoo {
       server 127.0.0.1:7090;
   }

   upstream odoochat {
       server 127.0.0.1:7093;
   }
   ```

   Keep `server_name abdinpharmacies.com`, TLS, public port 443, normal
   `location /` proxying and trusted forwarding headers. Replace the old
   `/longpolling` location for this domain with Odoo 19's WebSocket location:

   ```nginx
   location /websocket {
       proxy_pass http://odoochat;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_set_header X-Forwarded-Host $server_name;
       proxy_set_header X-Forwarded-For $remote_addr;
       proxy_set_header X-Forwarded-Proto https;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

   This explicitly preserves the observed trusted forwarding headers because
   location-level `proxy_set_header` directives override their inheritance.
   Adapt to the verified effective config rather than replacing a whole file.
   Do not blindly change every `9150` or `4053` occurrence across the server.
2. Through Odoo settings or supported ORM on the verified `ecom19` database,
   update the intended Website domain and `web.base.url` to
   `https://abdinpharmacies.com`. Set `web.base.url.freeze` to `True` when keeping
   the alternate `store` hostname, preventing administrator login there from
   changing the canonical base URL. Preserve the original values/existence in
   the recovery record. Review hostname-bound payment/OAuth callbacks; change
   external-provider settings only within explicit authorization.
3. Run `nginx -t`. On failure, do not reload; restore the changed files and URL
   settings from this operation and diagnose the reported error.
4. On success, run `systemctl reload nginx`, check its exit status and
   `systemctl is-active nginx`, and inspect bounded recent error logs. No Odoo
   restart, port reassignment, module upgrade, Git push, or DNS change is needed
   for this routing-only switch when existing prerequisites already hold.
5. Verify main-domain `/web/login`, `/shop`, `/ar/shop`, a real product page,
   images/assets, cart and redirects. Check visible English/Arabic content and
   selected database, not just HTTP 200. Verify a real WebSocket handshake
   (`101 Switching Protocols`) using the client version from the served assets.
   A normal HTTP GET to `/websocket` does not prove handshake success. Confirm
   `store` has the agreed behavior and main-domain links stay on the main domain.
   Do not create real paid orders merely for a smoke test.
6. Record completed checks, final hashes and URL values, the recovery directory,
   any unresolved issue, and completion time. Report the exact rollback target.
   If verification fails, stop further changes and restore this operation's
   baseline routing/settings; verify that restoration and report the failure.

## Rollback when asked to restore the previous setup

“Restore the previous setup” in this workflow means the recorded routing and
URL settings immediately before the specified cutover, not database contents.

1. Locate the exact cutover recovery record. If missing or multiple records make
   the target ambiguous, inspect available evidence and ask only for the missing
   target information. Never pretend historical port numbers are a full backup.
2. Recheck old backend health on its recorded ports and current effective config.
   Compare current files/settings against the recorded post-cutover values.
   Preserve unrelated later changes; if they conflict, prepare a scoped reversal
   rather than copying an old whole-file snapshot over them.
3. Restore the recorded main-domain routing. For the observed baseline, this is
   HTTP `9150`, realtime `4053`, and the previous `/longpolling` location, removing
   the cutover's `/websocket` location. Restore the exact original file only when
   no unrelated edits would be lost. Restore any `store` routing changed as part
   of that cutover too.
4. Restore only URL settings changed by the cutover, including prior parameter
   absence where applicable, through Odoo settings/ORM. Do not overwrite later
   intentional changes without resolving the conflict.
5. Run `nginx -t`, then reload only on success; verify service state, public login,
   old-backend routing, TLS, and `store` behavior. Record rollback results and
   paths. If the old backend is unhealthy, do not redirect users into it.
6. Leave `ecom19`, its orders, filestore, old-backend database, service ports, and
   code untouched. Orders created after cutover remain in `ecom19`; they do not
   appear automatically in the former backend. Identify any pending fulfillment
   handoff before routing back. Database restore, order migration, and service
   removal require separate explicit tasks.

## Sources

- [Odoo 19 deployment](https://www.odoo.com/documentation/19.0/administration/on_premise/deploy.html)
- [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html)
- [Nginx configuration reload](https://nginx.org/en/docs/beginners_guide.html)
