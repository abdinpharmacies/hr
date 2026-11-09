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
