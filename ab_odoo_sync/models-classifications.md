  Master Models
  These should not be passive-mirrored from branches. Keep them report-owned or sync as controlled business_model reference data. Branch facts should reference them by ID/code/serial.

  - ab_store, ab_store_ip, ab_replica_db
  - ab_product, ab_product_card, ab_product_barcode, ab_product_uom, ab_product_uom_category, ab_uom, ab_uom_type
  - ab_product_company, ab_product_origin, ab_product_group, ab_product_tag, ab_scientific_group, ab_usage_causes, ab_usage_manner
  - ab_customer, ab_customer_contact, ab_customer_contact_way
  - ab_hr_employee, ab_hr_department, ab_hr_job, ab_hr_job_occupied, ab_hr_region
  - ab_costcenter
  - ab_supplier and supplier setup models: contacts, discounts, brackets, payment types, notes, marketing, compensation
  - ab_contract, ab_contract_product_origin
  - ab_promo_program
  - ab_doctor, ab_product_doctor_prescription
  - ab_sales_channel
  - ab_employee_access, ab_employee_access_sales_role
  - ab_users as the report-side placeholder/dimension for branch res.users; do not sync res.users directly

  Passive Models Of High Value
  These are worth syncing from branches because they are branch-local facts: time, store, employee, customer snapshot, product, quantity, price, status, failures, or operational decisions.

  - ab_sales_header
  - ab_sales_line
  - ab_sales_return_header
  - ab_sales_return_line
  - ab_sales_lead
  - ab_sales_inventory
  - ab_sales_per_day
  - ab_product_rank, if POS recommendations/customer demand analysis matters
  - ab_product_priced, if branch-level product pricing readiness differs by branch
  - ab_transfer_header
  - ab_transfer_line
  - ab_transfer_request
  - ab_transfer_request_line
  - ab_transfer_receive_header
  - ab_transfer_receive_line
  - ab_transfer_smart_wizard, if you want to analyze smart-transfer planning behavior
  - ab_transfer_smart_product_line
  - ab_transfer_smart_line
  - ab_stock_recycling_header
  - ab_stock_recycling_line
  - ab_stock_recycling_need
  - ab_stock_recycling_dist
  - ab_sales_promo_report_line, if generated per branch and used for promotion effectiveness
  - ab_employee_access_sales_shift
  - ab_employee_access_sales_pos_session
  - ab_employee_access_sales_operation_log, but exclude or aggregate heartbeat rows unless you need detailed device/activity diagnostics

  Passive Models Of Low Or No Value
  Do not sync these for normal data collection/analysis. They are configuration, transient UI state, cache, sync plumbing, or report-generated artifacts.

  - ab_sales_pos_settings
  - ab_sales_pos_draft_cache
  - ab_sales_pos_replication_turn
  - ab_printer
  - ab_sales_per_day_sync_state
  - ab_sales_dashboard_sync_state
  - ab.sales.dashboard.snapshot
  - ab.sales.dashboard.collection.line
  - ab.sales.dashboard.user.line
  - ab.sales.dashboard.item.line
  - ab.sales.dashboard.invoice.line
  - ab.sales.dashboard.report.archive
  - ab.sales.dashboard.daily.store.fact
  - ab.sales.dashboard.daily.collection.fact
  - ab_sales_dashboard_daily_user_fact
  - ab.sales.dashboard.daily.item.fact
  - ab.sales.dashboard.fact.coverage
  - ab.sales.dashboard.sync.coverage
  - ab.sales.dashboard.report.telemetry
  - ab.sales.dashboard.fact.decision
  - ab.sales.dashboard.reconciliation.job
  - ab.sales.dashboard.reconciliation.chunk
  - ab_transfer_smart_source_stock_cache
  - ab_transfer_smart_stock_cache
  - ab_transfer_smart_sales_cache, unless you intentionally convert them into dated historical snapshots
  - Transient/API models: ab_sales_cashier_api, ab_sales_cashier_close_wizard, ab_sales_cashier_close_wizard_line, POS API models, report wizards
  - Sync/internal models: ab_odoo_sync_outbox, ab_odoo_sync_upload_source, ab_odoo_sync_upload_record, ab_odoo_sync_apply_profile, ab_odoo_sync_field_mapping, ab_odoo_sync_identity,
    ab_odoo_sync_branch_registry, ab_odoo_sync_upload_field_override

  - Infra models: queue.job, queue.job.channel, queue.job.function, queue.job.lock

  The core rule: sync branch facts, not global dimensions. ab_sales_header and ab_sales_line are high value; ab_product is a master dimension; POS drafts/settings/printers/sync states are low value
  unless you are debugging operations.

