# Ecommerce Demo Deployment Environment

Verified on 2026-10-21 in the `Africa/Cairo` timezone. Recheck all mutable state
before deployment. The values below identify this environment and contain no
passwords or private key material.

## Access and repositories

| Item | Value |
| --- | --- |
| Local worktree | `/opt/odoo19/custom-addons-ecommerce` |
| Local branch | `e_commerce` |
| Local Git origin | `git@github.com:abdinpharmacies/hr.git` |
| SSH command | `ssh ecommerce` |
| SSH alias config | `/home/abdin_02/.ssh/config` |
| SSH endpoint | `46.202.130.7:2222` |
| SSH user | `root` |
| SSH identity path | `/home/abdin_02/.ssh/ecomm` |
| Remote repository | `/opt/odoo19/custom-addons` |
| Remote branch | `e_commerce` |
| Remote Git origin | `git@github-support.com:abdinpharmacies/hr.git` |
| Last observed matching commit | `152633b6` |

The local and remote Git origin hostnames intentionally differ. `git ls-remote`
previously confirmed that both `e_commerce` branches had the same pushed commit.
The SSH key must be available to the local SSH agent. Odoo web credentials are
not SSH credentials. The recorded commit is historical context only.

## Odoo and website

| Item | Value |
| --- | --- |
| Website | `https://store.abdinpharmacies.com` |
| Systemd service | `odoo19.service` |
| Service unit | `/etc/systemd/system/odoo19.service` |
| Service user and group | `odoo19:odoo19` |
| Odoo executable | `/opt/odoo19/server/odoo-bin` |
| Python interpreter | `/opt/odoo19/venv19/bin/python3` |
| Odoo config | `/opt/odoo19/odoo19.conf` |
| Custom addons path | `/opt/odoo19/custom-addons` |
| Main log | `/opt/odoo19/odoo.log` |
| Database | `ecom19` |
| Filestore | `/opt/odoo19/.local/share/Odoo/filestore/ecom19` |
| Backup directory | `/opt/odoo19/backups` |
| Nginx config | `/etc/nginx/conf.d/odoo19.conf` |
| Odoo HTTP upstream | `127.0.0.1:7090` |
| Chat upstream | `127.0.0.1:7093` |
| PostgreSQL cluster | `16/main`, port `5432` |
| PostgreSQL data | `/var/lib/postgresql/16/main` |
| PostgreSQL log | `/var/log/postgresql/postgresql-16-main.log` |

Nginx uses certificate files under
`/etc/letsencrypt/live/abdinpharmacies.com`. The database is always `ecom19`,
even if an older message calls the demo database `demo`. Keep the database and
its filestore together for a full restore.

## Commands

Run local preflight checks in the local worktree:

```bash
git status --short --branch
git log --oneline origin/e_commerce..HEAD
git diff --check
```

Push the intended committed changes only after reviewing them:

```bash
git push origin e_commerce
```

Inspect the server repository before mutation:

```bash
ssh ecommerce 'git -C /opt/odoo19/custom-addons status --short --branch; git -C /opt/odoo19/custom-addons branch --show-current; git -C /opt/odoo19/custom-addons log -1 --oneline'
```

Compare the remote branch hash with the pushed local hash:

```bash
ssh ecommerce 'git -C /opt/odoo19/custom-addons ls-remote origin refs/heads/e_commerce'
```

Fast-forward the server checkout:

```bash
ssh ecommerce 'git -C /opt/odoo19/custom-addons pull --ff-only origin e_commerce'
```

Before a database upgrade, create a custom-format backup. Redirection must be
performed by the SSH/root shell because the destination directory is root-only:

```bash
ssh ecommerce 'backup_path=/opt/odoo19/backups/ecom19_before_$(date +%Y%m%d_%H%M%S).dump; umask 077; sudo -u postgres pg_dump -Fc -d ecom19 > "$backup_path" && printf "%s\n" "$backup_path"'
```

Record the generated filename, substitute its exact path below, and require a
successful result before upgrading:

```bash
ssh ecommerce 'pg_restore -l /opt/odoo19/backups/EXACT_BACKUP_FILE.dump >/dev/null'
```

For changes requiring an upgrade of `ab_ecommerce_storefront`, use:

```bash
ssh ecommerce 'sudo -u odoo19 /opt/odoo19/venv19/bin/python3 /opt/odoo19/server/odoo-bin -c /opt/odoo19/odoo19.conf -d ecom19 -u ab_ecommerce_storefront --stop-after-init --no-http --workers=0 --max-cron-threads=0 --logfile=/tmp/odoo19_storefront_upgrade.log'
```

Inspect the command exit status and the full upgrade log. For other affected
modules, replace only the comma-separated `-u` value and use a distinct `/tmp`
log filename.

Restart and verify the service:

```bash
ssh ecommerce 'systemctl restart odoo19.service && systemctl is-active odoo19.service'
```

Afterward, verify the exact deployed `HEAD`, remote status, bounded recent logs,
and the public routes. Avoid reproducing credentials or customer data from logs.

## Known module and storefront context

The storefront module is `ab_ecommerce_storefront`; its product-classification
dependency is `ab_website_sale_product`. Both were installed on `ecom19` when
last checked.

On 2026-10-21, the Arabic shop sidebar showed 77 items including “All products,”
all category labels were Arabic, and the Arabic product breadcrumb showed “كل
المنتجات.” These are historical observations, not permanent acceptance counts or
strings. The upgrade log also reported a separate missing `report_xlsx` module;
investigate it only when XLSX reports or the current deployment are affected.
