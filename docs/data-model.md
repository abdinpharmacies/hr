# 5. Data Model

## Main entities/models

## Sales entities
| Model | Important fields | Notes |
|---|---|---|
| `ab_sales_header` | `store_id`, `customer_id`, `status`, `eplus_serial`, `pos_client_token`, `push_state`, `line_ids` | Core sales header; idempotency token unique constraint; status lifecycle drives editability. |
| `ab_sales_line` | `header_id`, `product_id`, `qty_str`/`qty`, `uom_id`, `sell_price`, `net_amount`, `inventory_json`, `balance`, `unavailable_reason` | Holds line pricing and inventory batch payload used during push. |
| `ab_sales_return_header` | `origin_header_id`, `store_id`, `status`, `line_ids`, `total_return_value` | Return against an original ePlus invoice. |
| `ab_sales_return_line` | `header_id`, `std_id`, `itm_eplus_id`, `qty`, `qty_sold_source`, `max_returnable_source` | Includes source-unit/UoM conversion metadata. |
| `ab_sales_inventory` | `product_eplus_serial`, `store_id`, `balance`, `default_price` | Cached balances globally (`store_id=False`) and per POS store. |
| `ab_product_rank` | `product_id`, `store_id`, `customer_phone`, `rank_scope`, `score` | Ranking cache for product suggestions. |

## Master data entities
| Model | Important fields | Relationships |
|---|---|---|
| `ab_store` | `code`, `name`, `store_type`, `allow_sale`, `ip1..ip4`, `parent_id` | One2many `ab_store_ip`; referenced by most transactional headers. |
| `ab_replica_db` | `db_serial`, `return_allowed_days`, `allowed_sales_store_ids`, `default_sales_store_id` | Defines current replica policies by `odoo.conf` `db_serial`. |
| `ab_product` | `product_card_id`, `code`, `default_price`, `unit_l_id/unit_m_id/unit_s_id`, `uom_id` | `_inherits` from `ab_product_card`; conversion helpers between units. |
| `ab_product_card` | `name`, `origin`, `company_id`, `groups_ids`, `active` | Product master card fields shared across `ab_product` variants. |
| `ab_customer` | `code`, `name`, `mobile_phone`, `work_phone`, `address`, `default_store_id` | Customer master, linked from sales headers. |
| `ab_costcenter` | `code`, `name`, `user_id`, `password`, `work_email` | Used across HR and authorization helpers. |

## Inventory and movement entities
| Model | Important fields | Notes |
|---|---|---|
| `ab_inventory` | `store_id`, `source_id`, `qty`, `status`, `model_ref`, `res_id`, `header_ref` | Generic ledger rows tied to source document lines. |
| `ab_inventory_header` | `header_ref`, `store_id`, `to_store_id`, `line_ids`, pending counts | Grouped inventory movement record. |
| `ab_transfer_header` | `store_id`, `to_store_id`, `status`, `line_ids` | Transfer send/receive and reject states. |
| `ab_transfer_line` | `product_id`, `source_id`, `qty`, `qty_rejected`, `balance` | Operates on inventory source batches. |
| `ab_inventory_adjust_header` | `store_id`, `status`, `adjust_type`, `eplus_inv_id`, `line_ids` | ePlus stock adjustment document wrapper. |
| `ab_inventory_eplus` | `product_id`, `store_id`, `c_id`, `qty`, `sell_price` | Local snapshot of ePlus `Item_Class_Store`. |

## HR entities
| Model | Important fields | Notes |
|---|---|---|
| `ab_hr_employee` | (many fields), hierarchy/job/store links | Core HR employee model used by sales and attendance. |
| `ab_hr_job_occupied` | occupancy and termination fields | Extended in employee tools for termination notifications. |
| `ab_hr_application` | applicant identity/contact/job fields | Website and import intake target model. |
| `ab_hr_attendance_log` | `employee_id`, `check_time`, `check_type`, `device_serial`, `store_id` | Written by fingerprint sync job. |

## Messaging/integration entities
| Model | Important fields | Notes |
|---|---|---|
| `ab_telegram_chat_message` | `telegram_user_id`, `session_uuid`, `openai_messages_json`, `session_status`, `token_limit`, `token_count` | Used as AI session context storage. |
| `ab_user_telegram_link` | `telegram_user_id`, `user_id`, `status`, `pin`, `ai_context_token_limit` | Enforces one Telegram account per Odoo user and vice versa. |
| `ab.whatsapp.contact` | `wa_id`, `name`, `preferred_phone_number_id`, `last_message_*` | WhatsApp contact directory. |
| `ab.whatsapp.message` | `direction`, `contact_id`, `message_type`, `status`, `meta_message_id`, media/reply/reaction fields | Conversation/event log. |
| `ab.whatsapp.template` | `template_uid`, `name`, `language`, `status`, `components_payload` | Synced/submitted Meta templates. |
| `ab_odoo_replication_log` | `model_name`, `last_write_date`, `last_id`, `last_run` | Replication cursor checkpoint.

## Relationships between entities
- `ab_sales_header` 1:N `ab_sales_line`.
- `ab_sales_return_header` 1:N `ab_sales_return_line`.
- `ab_store` is referenced by sales/returns/transfers/inventory/HR attendance.
- `ab_product` is referenced by sales lines, transfer lines, inventory snapshots/ranks.
- `ab_customer` is optional on sales headers; phone snapshots are also stored on header fields.
- `ab_user_telegram_link` optionally links to `res.users`; `ab_telegram_chat_message` can link to `res.users` via `linked_user_id`.
- `ab.whatsapp.contact` 1:N `ab.whatsapp.message` (cascade delete).

## Lifecycle/state transitions

### Sales header (`ab_sales_header.status`)
- `prepending` -> `pending` -> `saved`
- Deletion is blocked unless `prepending`.
- Submit is blocked unless `pos_client_token` is present.

### Sales return header (`ab_sales_return_header.status`)
- `prepending` -> `pending` -> `saved`
- Return push requires original invoice saved and within allowed days.

### Transfer header (`ab_transfer_header.status`)
- `prepending` -> `pending` -> `saved` or `rejected`

### Generic inventory line (`ab_inventory.status`)
- `pending_main` <-> `pending_store` -> `saved`

### Telegram link (`ab_user_telegram_link.status`)
- `new` -> `awaiting_email` -> `awaiting_password` -> `linked` (or back to `new` on unlink/cancel)

### WhatsApp message status
- Outgoing status merge is monotonic (`sent`/`failed` -> `delivered` -> `read`), never downgraded.

## Data constraints and business rules
- `ab_sales_header.pos_client_token` unique (`models.Constraint`).
- `ab_replica_db.db_serial` unique and positive; return window minimum 1 day.
- `ab.whatsapp.contact.wa_id` unique.
- `ab.whatsapp.template.template_uid` unique.
- `ab_user_telegram_link` enforces unique `telegram_user_id` and unique `user_id`.
- `ab_product_rank` unique composite key by scope dimensions.

## Unclear from codebase
- Full ERD for every addon (62 modules) is not explicitly documented in-repo.
- Some referenced models/dependencies are external/missing in this repository (`ab_taxes`, `ab_employee`, `ab_eplus_replication`).
