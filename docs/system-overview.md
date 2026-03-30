# 1. System Overview

## What the system does
This codebase implements an Odoo 19 addon suite for a pharmacy retail operation. It manages sales, returns, inventory movement, product/customer/HR master data, and multiple integrations (ePlus MSSQL, remote Odoo replication, Telegram, WhatsApp).

Core business modules are under `ab_*` (for example: `ab_sales`, `ab_store`, `ab_product`, `ab_hr`, `ab_odoo_replication`).

## Main business purpose
- Run branch-level pharmacy sales/POS with near-real-time stock and pricing from ePlus.
- Keep replica databases synchronized with a control server (Odoo-to-Odoo replication).
- Support operational workflows for HR, visit compliance, applicant intake, and communication.

## Who uses it
| User Type | Typical Modules |
|---|---|
| Cashiers / POS operators | `ab_sales`, `ab_sales_cashier`, `ab_pos` |
| Sales managers / supervisors | `ab_sales`, `ab_sales_promo`, `ab_sales_contract` |
| Inventory / branch operations | `ab_inventory`, `ab_transfer`, `ab_inventory_adjust`, `ab_distribution_store` |
| HR team | `ab_hr`, `ab_hr_effects`, `ab_hr_applicant`, `ab_hr_fingerprint`, `ab_hr_org_chart` |
| IT / system admins | `ab_eplus_connect`, `ab_odoo_replication`, `ab_odoo_update`, `ab_wan`, `ab_whatsapp_api`, `ab_telegram_webhook` |

## Main capabilities
- Sales invoice creation and push to ePlus (`ab_sales/models/ab_sales_header.py`).
- Sales return posting with return-window policy from replica DB settings (`ab_sales/models/ab_sales_return_header.py`, `ab_store/models/ab_replica_db.py`).
- Store-scoped inventory caches and ranking for product search (`ab_sales/models/ab_sales_inventory.py`, `ab_sales/models/ab_product_rank.py`).
- Transfer and pending/saved inventory status lifecycle (`ab_transfer`, `ab_inventory`).
- Promotion and contract pricing overlays on sales (`ab_sales_promo`, `ab_sales_contract`).
- Inbound replication from a control Odoo via XML-RPC (`ab_odoo_replication`, `ab_odoo_connect`).
- Outbound upload jobs via queue (`ab_odoo_replication_upload`, `queue_job`).
- HR + org chart + fingerprint attendance + applicant website forms (`ab_hr*`).
- Telegram webhook/account linking/OpenAI read-only assistant (`ab_telegram_webhook`, `ab_user_extra`).
- WhatsApp Cloud API dashboard with webhook, templates, and media proxy (`ab_whatsapp_api`).

## Repository scale snapshot
- 62 installable addons detected via `__manifest__.py`.
- Mix of custom business modules and third-party technical modules (`queue_job`, `integration_queue_job`, `report_xlsx`, `muk_*`, `web_domain_field`).
