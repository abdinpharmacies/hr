# 4. Business Flows

## Flow A: POS Sale Submission to ePlus
### 1) User actions
1. Cashier uses POS UI (`ab_sales`/`ab_pos`) to select store, customer, and products.
2. POS submits payload with `header` + `lines` and optional `pos_client_token`.

### 2) Backend processing
1. `ab_sales_pos_api.pos_submit(payload)` validates payload and store permission.
2. Creates `ab_sales_header` + `ab_sales_line` in `prepending` state.
3. Calls `header.action_submit()`.
4. `action_submit()` enforces POS token requirement.
5. `action_push_to_eplus()` validates lines, employee, and connection.

### 3) Database interactions
- Local PostgreSQL:
  - Insert/update `ab_sales_header`, `ab_sales_line`, inventory JSON fields.
- ePlus MSSQL:
  - Insert into `sales_trans_h`.
  - Insert line rows into `sales_trans_d` with FIFO-like batch source handling.
  - Update store item inventory (`item_class_store`) and optional delivery info.

### 4) External integrations
- Uses `ab_eplus_connect.connect_eplus()` to the store/main MSSQL server.

### 5) Final outputs
- Local header gets `eplus_serial`, status `pending`, `push_state=success`.
- Cron (`ab_sales/data/ir_cron.xml`) later checks ePlus flag and marks status `saved`.

---

## Flow B: Sales Return Posting
### 1) User actions
1. User enters original invoice number (`origin_header_id`) and store.
2. Clicks load lines, edits return quantities, then submits return.

### 2) Backend processing
1. `action_load_lines()` reads original invoice lines from ePlus tables.
2. Maps source-unit quantities/prices into display UoM.
3. `action_push_to_eplus_return()` validates:
   - invoice exists and is saved in ePlus,
   - return window (`ab_replica_db.return_allowed_days`),
   - key line identifiers.

### 3) Database interactions
- Local PostgreSQL:
  - Writes `ab_sales_return_header`/`ab_sales_return_line`.
- ePlus MSSQL:
  - Updates return-related values on source line/header tables.
  - Writes return accounting side effects (including wallet/cash-store related effects in return logic).

### 4) External integrations
- ePlus MSSQL via `ab_eplus_connect`.

### 5) Final outputs
- Return status transitions from `prepending` -> `pending`/`saved`.
- Return IDs and amounts are persisted locally.

---

## Flow C: Cashier Save Pending Documents
### 1) User actions
1. Cashier opens cashier screen.
2. Fetches pending list and saves selected invoice/return.

### 2) Backend processing
1. `ab_sales_cashier_api.get_pending_invoices()` checks cashier groups.
2. Builds list from:
   - local pending `ab_sales_header`,
   - BConnect pending rows fallback,
   - local pending returns.
3. `save_pending_invoice(...)` routes to sale or return save path.

### 3) Database interactions
- Local PostgreSQL:
  - Marks matched local sales header saved after successful external save.
- ePlus MSSQL:
  - Updates pending sale status and wallet collection data.

### 4) External integrations
- ePlus MSSQL wallet/save operations.

### 5) Final outputs
- Returns API-like response with status: `saved`, `already_saved`, or `invalid_status`.

---

## Flow D: Inbound Odoo Replication (Control -> Replica)
### 1) User/system action
- Admin triggers replication manually or by cron (`ab_odoo_replication/views/cron_ab_odoo_replication.xml`).

### 2) Backend processing
1. `run_replication_schema()` executes ordered model replication groups.
2. `replicate_model()` reads remote metadata/records using XML-RPC `execute_kw`.
3. Maps many2one values and writes local records.
4. Updates replication cursor (`ab_odoo_replication_log`).

### 3) Database interactions
- Local PostgreSQL: upsert replicated master data models.
- Remote Odoo XML-RPC: `fields_get`, `search_read`, `search_count`.

### 4) External integrations
- `ab_odoo_connect.OdooConnectionSingleton` with encrypted password and XML-RPC auth.

### 5) Final outputs
- Replica master data updated.
- Cursor fields (`last_write_date`, `last_id`, `last_run`) advanced.

---

## Flow E: Inventory Adjustment Sync (ePlus)
### 1) User actions
1. User loads latest inventory snapshot into `ab_inventory_eplus`.
2. Filters/builds adjustment lines.
3. Pushes adjustment document.

### 2) Backend processing
1. `btn_get_eplus_inventory()` reads `Item_Class_Store` chunks.
2. Creates/updates local snapshot rows by store/product/class.
3. `btn_push_eplus_inventory()` checks qty consistency and negative guards.
4. Inserts/updates ePlus `inventory_h` and `inventory_d`; updates price on `Item_Class_Store`.

### 3) Database interactions
- Local: `ab_inventory_adjust_header`, `ab_inventory_adjust_line`, `ab_inventory_eplus`.
- ePlus: `inventory_h`, `inventory_d`, `Item_Class_Store`.

### 4) Final outputs
- Adjustment header receives `eplus_inv_id`; status progression reflects remote completion.

---

## Flow F: Applicant Website Submission
### 1) User actions
1. Public user opens `/jobs/apply` and fills applicant form.
2. Solves captcha and submits.

### 2) Backend processing
1. Controller validates captcha TTL and required fields.
2. Normalizes int/bool fields and nested experience/course arrays.
3. Upserts applicant by `(national_identity, job_id)`.

### 3) Database interactions
- Writes `ab_hr_application`, `ab_hr_experience`, `ab_hr_course` records.

### 4) Final outputs
- Redirect to `/jobs/apply/thanks` on success.
- Re-render with validation error on failure.

---

## Flow G: Telegram Link + AI Query
### 1) User actions
1. Telegram user talks to bot webhook (`/ab_telegram_webhook/webhook`).
2. Uses menu to link account (login + password/API key).
3. Sends natural-language data query.

### 2) Backend processing
1. Webhook delegates text to `ab_user_telegram_link.bot_process_message(...)`.
2. Link flow validates credentials and enforces one Telegram account per user.
3. AI flow:
   - Reads OpenAI settings from Odoo config,
   - Plans read-only model query,
   - Sanitizes domain/fields,
   - Executes `search_read` with user permissions,
   - Summarizes and stores session turns.

### 3) Data interactions
- Local: `ab_user_telegram_link`, `ab_telegram_chat_message` session context records.
- External: OpenAI `chat/completions` HTTP endpoint.

### 4) Final outputs
- Bot replies with menu/help/link status/data answer payload.

---

## Flow H: WhatsApp Webhook and Messaging
### 1) User/system actions
1. Meta webhook calls `/ab_whatsapp_api/webhook`.
2. Admin uses OWL dashboard to send text/media/template/reaction.

### 2) Backend processing
1. Webhook payload parsed by `ab.whatsapp.service.process_webhook_payload(...)`.
2. Contacts/messages are created; outgoing statuses are merged monotonically (`sent` -> `delivered` -> `read`).
3. Dashboard calls `api_*` methods for list/send/sync/edit/delete operations.

### 3) Data interactions
- Local: `ab.whatsapp.contact`, `ab.whatsapp.message`, `ab.whatsapp.template`.
- External: Meta Graph API endpoints for messages/templates/media.

### 4) Final outputs
- Updated conversation timeline in dashboard.
- Media served through `/ab_whatsapp_api/media/<id>` (system-admin constrained).
