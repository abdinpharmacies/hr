# 3. Modules and Responsibilities

This section covers major custom modules (business and integration). Third-party vendor modules (`queue_job`, `muk_*`, `report_xlsx`, `web_domain_field`) are listed where they affect architecture.

## Sales and POS domain

### `ab_sales`
- Responsibility: Core sales invoices/lines, ePlus push, status sync, POS support services, inventory cache/rank jobs.
- Important files:
  - `ab_sales/models/ab_sales_header.py`
  - `ab_sales/models/ab_sales_line.py`
  - `ab_sales/models/ab_sales_return_header.py`
  - `ab_sales/models/ab_sales_ui_api.py`
  - `ab_sales/models/ab_sales_pos_api.py`
  - `ab_sales/data/ir_cron.xml`
- Dependencies: `ab_customer`, `ab_product`, `ab_store`, `ab_eplus_connect`, `ab_widgets`, `abdin_et`.
- Key logic:
  - `pos_client_token` uniqueness for idempotent submit.
  - `action_push_to_eplus` inserts `sales_trans_h/sales_trans_d` then consumes inventory.
  - Cron sync marks local pending invoices saved when remote flag closes.

### `ab_sales_cashier`
- Responsibility: Cashier view/API for pending invoices and return-save operations.
- Important files:
  - `ab_sales_cashier/models/ab_sales_cashier_api.py`
  - `ab_sales_cashier/models/ab_sales_cashier_close_wizard.py`
  - `ab_sales_cashier/tests/test_cashier_api.py`
- Dependencies: `ab_sales`.
- Key logic:
  - Merges pending data from local Odoo + BConnect fallback.
  - Save path is idempotent (`saved` vs `already_saved`) and role-gated.

### `ab_pos`
- Responsibility: Simple OWL POS client action and lightweight transient API.
- Important files:
  - `ab_pos/models/ab_pos_api.py`
  - `ab_pos/static/src/ab_pos_simple/*`
- Dependencies: `ab_sales`, `ab_product`, `ab_customer`, `ab_store`.
- Key logic:
  - Safe domain/field filtering before search_read.
  - Minimal `create_sale(payload)` flow.

### `ab_sales_promo`
- Responsibility: Promotion application on invoices/lines with price/totals override.
- Important files:
  - `ab_sales_promo/models/ab_sales_header_promo_inherit.py`
  - `ab_sales_promo/models/ab_sales_pos_api_promo.py`
- Dependencies: `ab_sales`, `ab_promo_program`.
- Key logic:
  - Computes `available_program_ids` and `promo_discount_amount`.
  - Auto-apply when exactly one effective promo is eligible.

### `ab_sales_contract`
- Responsibility: Contract pricing/cost-sharing overlays for sales and returns.
- Important files:
  - `ab_sales_contract/models/ab_contract.py`
  - `ab_sales_contract/models/ab_sales_header_inherit.py`
  - `ab_sales_contract/models/ab_sales_line_inherit.py`
  - `ab_sales_contract/models/ab_sales_return_header_inherit.py`
- Dependencies: `ab_sales`.
- Key logic:
  - Contract discount source resolution (rule vs origin default).
  - Computes `cust_pay` / `company_pay` and net totals.

## Product, inventory, and store domain

### `ab_product`
- Responsibility: Product master + card model + UoM conversion logic.
- Important files:
  - `ab_product/models/ab_product.py`
  - `ab_product/models/ab_product_card.py`
- Dependencies: `base`.
- Key logic:
  - `_inherits` on `ab_product_card`.
  - `qty_to_small` / `qty_from_small` conversion guards.

### `ab_product_source`
- Responsibility: Product source batches/prices/expiration and conversions.
- Important files:
  - `ab_product_source/models/ab_product_source.py`
- Dependencies: `ab_product`, `ab_taxes`.
- Key logic: Source-level cost/price data used by inventory/transfer flows.

### `ab_inventory`
- Responsibility: Internal inventory ledger and status transitions (`pending_main`, `pending_store`, `saved`).
- Important files:
  - `ab_inventory/models/ab_inventory.py`
  - `ab_inventory/models/ab_inventory_process.py`
  - `ab_inventory/models/ab_inventory_header.py`
- Dependencies: `ab_product_source`, `ab_store`.
- Key logic:
  - `inventory_write(...)` helper standardizes inventory writes from multiple documents.

### `ab_transfer`
- Responsibility: Inter-store transfer send/receive/reject workflow.
- Important files:
  - `ab_transfer/models/transfer_header.py`
  - `ab_transfer/models/transfer_line.py`
- Dependencies: `ab_store`, `ab_product`, `ab_inventory`, `web_domain_field`, `ab_employee`.
- Key logic:
  - Writes paired inventory movements for source and destination stores.
  - Partial rejection handling by `qty_rejected`.

### `ab_inventory_adjust`
- Responsibility: ePlus inventory reconciliation and adjustment push/get.
- Important files:
  - `ab_inventory_adjust/models/ab_inventory_adjust_header.py`
  - `ab_inventory_adjust/models/ab_inventory_adjust_header_get.py`
  - `ab_inventory_adjust/models/ab_inventory_adjust_header_push.py`
  - `ab_inventory_adjust/models/ab_inventory_eplus.py`
- Dependencies: `ab_product`, `ab_store`, `ab_eplus_connect`, `ab_eplus_replication`, `ab_hr`.
- Key logic:
  - Pulls `Item_Class_Store` snapshots, builds adjustment lines.
  - Pushes adjustments to `inventory_h`/`inventory_d` and updates ePlus prices.

### `ab_distribution_store`
- Responsibility: Distribution sales-like flow with local balance decrements.
- Important files:
  - `ab_distribution_store/models/distribution_header.py`
  - `ab_distribution_store/models/distribution_line.py`
  - `ab_distribution_store/models/distribution_inventory.py`
  - `ab_distribution_store/tests/test_distribution_store.py`
- Dependencies: `base`.
- Key logic:
  - Atomic-like inventory delta logic on line create/write/unlink.

### `ab_store`
- Responsibility: Store master, replica DB policy, login IP controls.
- Important files:
  - `ab_store/models/ab_store.py`
  - `ab_store/models/ab_replica_db.py`
  - `ab_store/models/res_users_inherit.py`
- Dependencies: `base`.
- Key logic:
  - Replica DB serial + allowed/default sales stores.
  - `_check_credentials` enforces IP allowlist unless privileged.

### `ab_customer`
- Responsibility: Customer master and contact data.
- Important files: `ab_customer/models/ab_customer.py`.
- Dependencies: `ab_costcenter`, `ab_store`, `mail`.
- Key logic: Search helper includes phone/code/address patterns.

### `ab_costcenter`
- Responsibility: Cost center/employee-like master and second-auth helper mixin.
- Important files:
  - `ab_costcenter/models/costcenter.py`
  - `ab_costcenter/models/ab_costcenter_second_auth.py`
- Dependencies: `base`, `mail`.
- Key logic: Optional second authentication via `user_code/password`.

## HR and staffing domain

### `ab_hr`
- Responsibility: Employee/job/department/history/manpower core models.
- Important files: `ab_hr/models/*.py`.
- Dependencies: `ab_costcenter`, `ab_store`, `mail`, `abdin_et`.
- Key logic: HR hierarchy, job occupancy, user relations.

### `ab_hr_effects`
- Responsibility: HR effects and approval/workflow-like logic.
- Important files: `ab_hr_effects/models/*.py`.
- Dependencies: `ab_hr`, `ab_costcenter`, `ab_store`.
- Key logic: Effect wizard and mixin behavior on employees.

### `ab_hr_fingerprint`
- Responsibility: ZK attendance device sync and logs.
- Important files:
  - `ab_hr_fingerprint/models/ab_hr_fingerprint_device.py`
  - `ab_hr_fingerprint/data/download_data.xml`
- Dependencies: `ab_hr`.
- Key logic: Cron reads device logs and creates attendance entries.

### `ab_hr_applicant`
- Responsibility: Website applicant/job post flow + MSSQL import support.
- Important files:
  - `ab_hr_applicant/controllers/ab_hr_application_controller.py`
  - `ab_hr_applicant/controllers/job_post_controller.py`
  - `ab_hr_applicant/models/mssql_import.py`
- Dependencies: `ab_hr`, `ab_cities`, `website`, `mail`.
- Key logic: Captcha, required-field validation, applicant upsert by national ID + job.

### `ab_hr_org_chart`
- Responsibility: Employee org chart JSON APIs.
- Important files: `ab_hr_org_chart/controllers/hr_org_chart.py`.
- Dependencies: `ab_hr`.
- Key logic: Access-checked manager/subordinate graph endpoints.

## Integration and replication domain

### `ab_eplus_connect`
- Responsibility: MSSQL connector abstraction and pooled/reconnecting cursors.
- Important files: `ab_eplus_connect/models/ab_eplus_connect.py`.
- Dependencies: `base`.
- Key logic:
  - Supports `pyodbc` or `pymssql`.
  - Connection probe + validation timeouts + reconnect wrappers.

### `ab_eplus_collect_customers`
- Responsibility: Pull spare customers from branch DBs into main ePlus DB.
- Important files:
  - `ab_eplus_collect_customers/models/ab_eplus_collect_customers.py`
  - `ab_eplus_collect_customers/data/cron_ab_eplus_collect_customers.xml`
- Dependencies: `ab_eplus_connect`, `ab_store`.

### `ab_eplus_replication_contract`
- Responsibility: Sync ePlus contracts into local `ab_contract`.
- Important files: `ab_eplus_replication_contract/models/ab_contract_inherit.py`.
- Dependencies: `ab_eplus_connect`, `ab_sales_contract`.

### `ab_odoo_connect`
- Responsibility: XML-RPC singleton connection to central Odoo.
- Important files: `ab_odoo_connect/ab_odoo_connect.py`.
- Dependencies: `base`.

### `ab_odoo_replication`
- Responsibility: Inbound replication engine + replication cursors + write-protection layer.
- Important files:
  - `ab_odoo_replication/models/ab_odoo_replication.py`
  - `ab_odoo_replication/models/ab_odoo_replication_run.py`
  - `ab_odoo_replication/models/ab_odoo_replication_log.py`
  - `ab_odoo_replication/models_inherit/models_inherit.py`
- Dependencies: HR/product/customer/promo modules + `integration_queue_job`.
- Key logic:
  - Ordered schema replication (`run_replication_schema`).
  - Blocks manual CRUD on replicated masters unless replication context.

### `ab_odoo_replication_upload`
- Responsibility: Outbound upload to central Odoo via queue jobs.
- Important files: `ab_odoo_replication_upload/models/ab_odoo_replication_upload.py`.
- Dependencies: `ab_odoo_connect`, `queue_job`.

### `ab_odoo_update`
- Responsibility: Pull code and trigger restart/upgrade helpers.
- Important files:
  - `ab_odoo_update/models/ab_odoo_update.py`
  - `ab_odoo_update/views/cron_ab_odoo_update.xml`
- Dependencies: `base`.

### `ab_wan`
- Responsibility: Fetch public WAN IP and update ePlus store records.
- Important files:
  - `ab_wan/models/ab_wan_get.py`
  - `ab_wan/models/ab_wan_update_eplus.py`
- Dependencies: `ab_eplus_connect`, `ab_store`.

## Communications and web modules

### `ab_telegram_webhook`
- Responsibility: Telegram webhook receiver and setup hook.
- Important files:
  - `ab_telegram_webhook/controllers/main.py`
  - `ab_telegram_webhook/models/telegram_webhook_setup.py`
  - `ab_telegram_webhook/models/telegram_chat_message.py`
- Dependencies: `base` (+ `telebot` external dep).

### `ab_user_extra`
- Responsibility: Telegram account linking, PIN, AI read-only query flow over Odoo models.
- Important files:
  - `ab_user_extra/models/user_telegram_link.py`
  - `ab_user_extra/tests/test_user_telegram_link.py`
- Dependencies: `ab_telegram_webhook`.
- Key logic:
  - 1:1 Telegram?Odoo user linking.
  - AI session token limits and domain/field safety sanitization.

### `ab_whatsapp_api`
- Responsibility: WhatsApp Cloud API admin dashboard and webhook processor.
- Important files:
  - `ab_whatsapp_api/models/whatsapp_service.py`
  - `ab_whatsapp_api/controllers/main.py`
  - `ab_whatsapp_api/static/src/dashboard/*`
  - `ab_whatsapp_api/tests/test_ab_whatsapp_api.py`
- Dependencies: `base`, `web` (+ `requests`).
- Key logic:
  - Template sync/send, text/media/reaction send, status merge, media proxy.

### `ab_website`
- Responsibility: Website branding/debranding and menu/footer patching on install.
- Important files:
  - `ab_website/models/website_setup.py`
  - `ab_website/views/website_debrand.xml`
  - `ab_website/data/setup.xml`
- Dependencies: `website`.

## Supporting/utility modules (custom)
- `ab_offer_eplus_cycle`: replicate offer cycle into ePlus `Customer_Items`.
- `ab_visit_report`: large compliance checklist + Telegram notification on submit.
- `ab_employee_tools`: employee tool issuance + termination notifications.
- `ab_announcement`: announcement records with link generation.
- `ab_widgets`: OWL field widgets and many2x behavior patches.
- `abdin_telegram`, `abdin_js`, `abdin_css`: legacy communication/UI customizations.

## Third-party technical modules included
- `queue_job`, `integration_queue_job`: async job framework.
- `report_xlsx`: XLSX report base.
- `web_domain_field`: computed domain helper.
- `muk_web_*`: backend theme/widgets.
