# 11. AI-Friendly Summary

## System purpose

Odoo 19 addon suite for pharmacy branch operations: sales/POS, returns, inventory movement, master data, HR workflows,
and multi-system integrations (ePlus MSSQL, central Odoo replication, Telegram, WhatsApp).

## Architecture style

- Modular Odoo monolith (many addons in one repository).
- Server-side business logic in ORM models + transient service models.
- Hybrid persistence/integration: Odoo PostgreSQL + direct ePlus MSSQL SQL.
- XML-RPC used for central Odoo replication.

## Core modules

- Sales core: `ab_sales`, `ab_sales_cashier`
- Pricing overlays: `ab_sales_promo`, `ab_sales_contract`, `ab_promo_program`
- Master/inventory: `ab_store`, `ab_product`, `ab_customer`, `ab_inventory`, `ab_transfer`, `ab_inventory_adjust`
- HR stack: `ab_hr`, `ab_hr_effects`, `ab_hr_fingerprint`, `ab_hr_applicant`, `ab_hr_org_chart`
- Integration stack: `ab_eplus_connect`, `ab_odoo_connect`, `ab_odoo_replication`, `ab_odoo_replication_upload`,
  `ab_offer_eplus_cycle`
- Messaging: `ab_telegram_webhook`, `ab_user_extra`, `ab_whatsapp_api`

## Main entities

- Sales: `ab_sales_header`, `ab_sales_line`, `ab_sales_return_header`, `ab_sales_return_line`
- Inventory: `ab_inventory`, `ab_inventory_header`, `ab_sales_inventory`, `ab_inventory_eplus`
- Master: `ab_store`, `ab_replica_db`, `ab_product`, `ab_product_card`, `ab_customer`, `ab_costcenter`
- Replication: `ab_odoo_replication_log`
- Messaging: `ab_user_telegram_link`, `ab_telegram_chat_message`, `ab.whatsapp.contact`, `ab.whatsapp.message`,
  `ab.whatsapp.template`

## Critical business rules

- Sales submit allowed only for POS-created headers with `pos_client_token`.
- `pos_client_token` is unique to prevent duplicate invoices.
- Sales/returns use status lifecycles (`prepending` -> `pending` -> `saved`).
- Return posting enforces policy window from `ab_replica_db.return_allowed_days`.
- Replica DB allowed/default stores control sales store selection.
- Replicated master models are protected against manual CRUD outside replication context.
- WhatsApp APIs and Telegram link model are admin/system-access constrained.

## Important constraints and assumptions

- Requires live MSSQL connectivity to ePlus for core sales/return operations.
- Requires correct `odoo.conf` keys (`db_serial`, ePlus credentials, replication credentials, etc.).
- Uses legacy XML-RPC for Odoo replication and some legacy JS modules (`odoo.define`) still exist.
- Repository is addons-only; full deployment scripts/service config are **Unclear from codebase**.
- Some manifest dependencies are unresolved in this repository (`ab_taxes`, `ab_employee`, `ab_eplus_replication`).
