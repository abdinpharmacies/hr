# Odoo 19 Replica Addons

This repository is a multi-addon Odoo 19 codebase for Abdin Pharmacies operations.

It combines:
- Sales and POS workflows with direct ePlus (MSSQL) posting
- Master data and replication from a central Odoo server
- HR, applicant, attendance, and operational reporting modules
- Messaging integrations (Telegram, WhatsApp)

## Documentation

Detailed engineering documentation is in `docs/`:
- `docs/system-overview.md`
- `docs/architecture.md`
- `docs/modules.md`
- `docs/business-flows.md`
- `docs/data-model.md`
- `docs/setup-and-run.md`
- `docs/ai-summary.md`

## Scope Notes

- This repository contains addons only (not the full Odoo server source).
- Some runtime details (exact `odoo.conf`, service wiring, deployment scripts outside this repo) are **Unclear from codebase**.

# Steps for FastAPI INstallation and Configration

db_user = crm_messaging_callcenter
db_password = abdin#dev$team

## To add the token manually:

1. Reload your PyCharm Odoo process and refresh the browser.
2. In Settings, activate developer mode.
3. Open Technical → Parameters → System Parameters.
4. Create or edit the parameter with key:
   ab_crm_sales_workspace.telegram_token.1.tg-callcenter
5. Paste your complete BotFather token into Value, then save.
6. Open Sales → Configurations → Telegram Connection and click Prepare connection.

## Queue setup needs your local administrator password. Run:

sudo -u postgres createuser --no-createdb --no-createrole --no-superuser --pwprompt crm_messaging_callcenter
sudo -u postgres createdb --owner=crm_messaging_callcenter crm_messaging_callcenter
cd /opt/odoo19/worktrees/callcenter19/crm_messaging_gateway
/home/abdin_04/.config/crm-messaging/venv/bin/python -m app.local_setup /home/abdin_04/.config/crm-messaging/config.json --username abdin_callcenter_bot --from-odoo --bootstrap /home/abdin_04/.config/crm-messaging/bootstrap.json

Enter bot ID 8933526980. For the hidden queue DSN, use:

postgresql://crm_messaging_callcenter:PASSWORD@127.0.0.1:5432/crm_messaging_callcenter

Use your newly created password, URL-encoding special characters. Keep credentials in your terminal.


