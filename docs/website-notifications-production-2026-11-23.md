# Production order notifications after endpoint reinstall

> Historical record: versions, deployment state and validation results below describe the dated work only. Temporary QA scripts/evidence may have been removed. For the current order-status button and login-return behavior, use [the current guide](website-order-status-links.md). This record does not establish a current production rollout.

This replaces earlier endpoint values in website-callcenter-production-setup.md for the store.abdinpharmacies.com connection. Production was diagnosed read-only. Applying files, upgrading production and activating the worker are manual operator actions.

## Verified identity and local preparation

A read-only check after the user's reinstall found one visible assigned endpoint, Production Website, website Abdin Pharmacies, company ABDIN PHARMACIES, source `62c18ac9-3a5b-472d-a75c-86d8edb575f5`. Enabled is on; Chat Enabled and Outgoing Enabled are off. Bridge Operator is Callcenter Support; Live Chat Channel is empty. The installed source adapter remains 19.0.1.5.1 and storefront remains 19.0.1.0.0. Capabilities responds successfully with v4 support.

This machine has a new local messaging account and matching private gateway entry, code `website-production-reinstalled`, for that exact source. Both intake and outgoing are disabled. No worker restart was performed. Previous website-production and website-production-current identities and message history were preserved. Do not enable the earlier prepared website-production-current: its 2f3d source predates the reinstall. The original website-production source starts a4e63 and is also historical.

The receiver service user, branch and company were copied using normal ORM operations from the existing production account. A private gateway backup was made next to config-website-pilot.json. No credentials are included in release files or this document.

## Bridge operator validation

For order notifications only, keep Chat Enabled and Outgoing Enabled off. With adapter 19.0.1.5.2, this does not disable native customer order chatter. That chatter retains Odoo ownership checks and existing dispatch closure but does not wait for Callcenter receipt. Native comments saved with forwarding off are not later backfilled automatically.

If the optional Live Chat bridge is enabled later, set Bridge Operator to Callcenter Support, not admin or the exchange service user. The operator must be active, internal, allowed in ABDIN PHARMACIES, and must not have Settings administrator access. In Live Chat, open the channel used by the website, add Callcenter Support under Operators, and select that same channel on the endpoint. A final read-only check confirmed Callcenter Support has no effective Settings administrator group and differs from the exchange service user. Current notification capabilities pass validation. The service credential could not list Live Chat channels, so channel membership was not verified remotely. This is required only for the bridge, not notification-only intake.

## Transfer and inspect the release

The prepared bundle is `/tmp/ecommerce-notifications-20261123.tar.gz` on the development machine. Copy it to production as hassan (commands run on the development machine):

```bash
scp -P 2222 /tmp/ecommerce-notifications-20261123.tar.gz hassan@46.202.130.7:~/
```

Then on production:

```bash
umask 077
mkdir -p ~/ecommerce-notifications-20261123
cd ~/ecommerce-notifications-20261123
tar -xzf ~/ecommerce-notifications-20261123.tar.gz
sha256sum -c SHA256SUMS
sudo python3 -B patch_storefront.py --root /opt/odoo19/custom-addons/ab_ecommerce_storefront
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d ecom19 -f audit_ecommerce.sql
```

The preview requires exact known production hashes for all four storefront files, or recognizes all four already patched. Unknown or mixed versions stop without replacing files. Review the audit before activation: unexpected backlog or orders present under both old and new sources require reconciliation; never force acknowledgement, reset UUIDs or move historical messages to a different account. Uninstalling may have removed source integration metadata; this audit cannot reconstruct it. Use a pre-uninstall backup if historical reconciliation is needed.

## Apply the targeted production upgrade

Use a short maintenance window. These commands are for the operator; they have not been executed by the agent. Do not run the module upgrade concurrently with live Odoo workers. The backups contain private business data; keep the directory private and retain the filestore backup with the database backup.

```bash
cd ~/ecommerce-notifications-20261123
sudo systemctl stop odoo19.service
sudo -u postgres pg_dump -Fc -d ecom19 > ecom19-before-notifications.backup
sudo tar -C /opt/odoo19/custom-addons -czf addons-before-notifications.tar.gz ab_ecommerce_storefront ab_storefront_callcenter_adapter
```

Determine the filestore path under the production service account and back it up:

```bash
odoo_data_dir="$(sudo -u odoo19 /opt/odoo19/venv19/bin/python3 -B - <<'PYTHON'
import sys
sys.path.insert(0, '/opt/odoo19/server')
from odoo.tools import config
config.parse_config(['-c', '/opt/odoo19/odoo19.conf'])
print(config['data_dir'])
PYTHON
)"
sudo test -d "$odoo_data_dir/filestore/ecom19"
sudo tar -C "$odoo_data_dir" -czf filestore-before-notifications.tar.gz filestore/ecom19
```

Require successful exit from each backup command before proceeding. Then:

```bash
sudo python3 -B patch_storefront.py --root /opt/odoo19/custom-addons/ab_ecommerce_storefront --apply
sudo tar -C /opt/odoo19/custom-addons -xzf ab_storefront_callcenter_adapter-19.0.1.5.2.tar.gz
sudo chown -R odoo19:odoo19 /opt/odoo19/custom-addons/ab_storefront_callcenter_adapter
sudo -u odoo19 /opt/odoo19/venv19/bin/python3 /opt/odoo19/server/odoo-bin -c /opt/odoo19/odoo19.conf -d ecom19 -u ab_ecommerce_storefront,ab_storefront_callcenter_adapter --workers=0 --max-cron-threads=0 --http-port=5169 --gevent-port=5172 --stop-after-init --logfile=/opt/odoo19/website-notifications-upgrade.log
```

Use unused alternate ports. Review the upgrade log and require successful exit before starting Odoo:

```bash
sudo tail -n 80 /opt/odoo19/website-notifications-upgrade.log
sudo systemctl start odoo19.service
sudo systemctl status odoo19.service --no-pager
```

If an upgrade fails, preserve the logs and backups and diagnose before starting workers on a partially upgraded database. Do not uninstall/reinstall again. A rollback requires restoring the matching database, filestore and addon backup together, not overwriting source files alone.

## Production Odoo settings and verification

1. Sign in as admin with ABDIN PHARMACIES selected. Open Callcenter Endpoints. The 1.5.2 rule allows Settings administrators to see endpoints in selected companies, including endpoints owned by the dedicated exchange user.
2. Open the existing Production Website record. Preserve the source UUID above and the dedicated exchange service user. Enabled stays on. Chat Enabled and Outgoing Enabled stay off for notifications only. Leave the Live Chat fields optional.
3. Verify installed versions: adapter 19.0.1.5.2 and storefront 19.0.1.0.1.
4. Before enabling the Callcenter worker, verify an authorized customer's order page accepts a native comment while the worker is inactive and does not show the Callcenter acknowledgement waiting text. Check English and Arabic. Existing dispatch closure and unauthorized-order denials must remain intact.
5. Checkout keeps normal Odoo payment, price and stock validations. Callcenter receipt adds no purchase approval, payment validation, stock write or automatic POS/invoice operation.

## Activate on this callcenter machine after production verification

1. In local Odoo, open the messaging account with code `website-production-reinstalled`. Enable intake. Keep Outgoing Enabled off. Do not change its source, branch, company, channel or service user.
2. In the private `/home/abdin_04/.config/crm-messaging/config-website-pilot.json`, change only `accounts.website-production-reinstalled.enabled` to true. Keep its `sending_enabled` false. Preserve all global, pilot, Telegram and WhatsApp settings. The old production source can be disabled for polling after auditing its backlog; preserve its Odoo account and historical queue records.
3. Restart only the Website worker and inspect it:

```bash
systemctl --user restart crm-messaging-pilot-website.service
systemctl --user status crm-messaging-pilot-website.service --no-pager
journalctl --user -u crm-messaging-pilot-website.service -n 80 --no-pager
cd /opt/odoo19/worktrees/callcenter19/crm_messaging_gateway
CRM_MESSAGING_CONFIG=/home/abdin_04/.config/crm-messaging/config-website-pilot.json /home/abdin_04/.config/crm-messaging/venv/bin/python -B -m app.ops status
```

4. Verify a deliberate new demo order produces one pending source notification and exactly one receiver capture, then becomes acknowledged. The native order must confirm even when this worker is stopped. Do not use the historical pilot review/ready entries as a new acceptance test, and do not force retries for uncertain messages.

A complete new two-server soak on this configuration has not been run. The current 1.5.2 focused source tests passed with one optional Customer API skip; the older full soak covers 1.5.1 only.
