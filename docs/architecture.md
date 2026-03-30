# 2. Architecture Overview

## High-level architecture
The system is an Odoo monolith extended by many addons, with two external data planes:

1. **ePlus MSSQL plane**
- Read/write business transactions and inventory (`ab_eplus_connect` based modules).

2. **Control Odoo plane**
- Inbound/outbound replication between central and replica Odoo servers (`ab_odoo_connect`, `ab_odoo_replication`, `ab_odoo_replication_upload`).

```text
User UI (Odoo web, OWL, website)
        |
        v
Odoo Models/Transient APIs (ab_sales_*, ab_hr_*, ...)
        |
        +--> PostgreSQL (Odoo ORM models)
        |
        +--> ePlus MSSQL (pyodbc/pymssql via ab_eplus_connect)
        |
        +--> Control Odoo XML-RPC (ab_odoo_connect)
        |
        +--> External messaging APIs (Telegram/WhatsApp)
```

## Main components
| Component | Responsibility | Key Paths |
|---|---|---|
| Odoo business models | Core domain logic and data persistence | `ab_*/models/*.py` |
| Web/HTTP controllers | Public/user routes (job portal, webhooks, media) | `ab_*/controllers/*.py` |
| OWL/frontend actions | POS, cashier, WhatsApp dashboard UI actions | `ab_sales/static/src/*`, `ab_sales_cashier/static/src/*`, `ab_whatsapp_api/static/src/*` |
| ePlus connector | MSSQL connectivity with pooling and reconnect wrappers | `ab_eplus_connect/models/ab_eplus_connect.py` |
| Odoo connector | XML-RPC singleton connector to control Odoo | `ab_odoo_connect/ab_odoo_connect.py` |
| Scheduled jobs | Status sync, balances, replication, offer sync, backups | `*/data/*.xml`, `*/views/*cron*.xml` |

## How components interact
- Sales/POS logic calls transient APIs (`ab_sales_pos_api`, `ab_sales_ui_api`) and writes `ab_sales_header` + `ab_sales_line`.
- Submit flow pushes invoice/lines to ePlus SQL tables (`sales_trans_h`, `sales_trans_d`) then updates local status.
- Cron jobs read ePlus flags and close pending documents locally (`ab_sales_header.cron_update_status_from_store`).
- Replication modules call remote Odoo via XML-RPC `execute_kw`, map values, and write with replication context.
- Messaging modules expose public webhooks and call model services (`ab_telegram_webhook`, `ab_whatsapp_api`).

## Request/data flow across the system
### A) POS invoice flow
1. OWL POS/UI calls transient methods (`ab_sales_pos_api.pos_submit`).
2. Odoo creates local header/lines (status `prepending`).
3. `action_submit` -> `action_push_to_eplus` inserts ePlus header/details.
4. Local header becomes `pending`; periodic cron checks ePlus `sth_flag='C'` and marks `saved`.

### B) Return flow
1. User loads original invoice lines from ePlus by `origin_header_id`.
2. System validates return days using `ab_replica_db.return_allowed_days`.
3. Push updates ePlus return and accounting-related tables; local return status moves to `pending/saved`.

### C) Replication flow
1. Scheduled/manual replication runs ordered `replicate_model` calls.
2. Records are read from control Odoo via XML-RPC.
3. Local records are upserted with many2one mapping and cursor tracking (`ab_odoo_replication_log`).

---

# 6. API / Interfaces

## HTTP endpoints (controllers)
| Route | Method/Auth | Purpose | File |
|---|---|---|---|
| `/ab_whatsapp_api/webhook` | `GET` public | Meta webhook verification | `ab_whatsapp_api/controllers/main.py` |
| `/ab_whatsapp_api/webhook` | `POST` public | Receive WhatsApp webhook payload | `ab_whatsapp_api/controllers/main.py` |
| `/ab_whatsapp_api/media/<int:message_id>` | `GET` user | Admin-only media proxy/download | `ab_whatsapp_api/controllers/main.py` |
| `/ab_telegram_webhook/webhook` | `GET` public | Telegram health ping | `ab_telegram_webhook/controllers/main.py` |
| `/ab_telegram_webhook/webhook` | `POST` public | Telegram message processing | `ab_telegram_webhook/controllers/main.py` |
| `/jobs/*` routes | public | Applicant forms, captcha, submit, listing | `ab_hr_applicant/controllers/*.py` |
| `/hr/get_org_chart` + related | user/json | Org chart data APIs | `ab_hr_org_chart/controllers/hr_org_chart.py` |
| `/react/pos/data`, `/react/pos/submit` | user/json | Demo React POS payload/submit | `react_embed_demo/controllers/main.py` |
| `/get_idle_time/timer` | user/json | Idle timeout config for frontend | `auto_logout_idle_user_odoo/controllers/auto_logout_idle_user_odoo.py` |

## Internal model interfaces used by UI/RPC
| Model | Function | Purpose |
|---|---|---|
| `ab_sales_pos_api` | `pos_submit(payload)` | Create/submit POS invoice with token idempotency |
| `ab_sales_pos_api` | `pos_product_details`, `pos_barcode_products` | Product + stock/balance details |
| `ab_sales_ui_api` | `search_products`, `apply_products` | POS search and line application |
| `ab_sales_ui_api` | `pos_customer_insights`, `pos_customer_invoices` | Customer history and last invoice data |
| `ab_sales_cashier_api` | `get_pending_invoices`, `save_pending_invoice` | Cashier settlement/save flow |
| `ab_whatsapp.service` | `api_*` methods | Contact/template/send/webhook processing |
| `ab_pos.api` | `get_stores/search_products/search_customers/create_sale` | Simplified POS integration API |
| `ab_user_telegram_link` | `bot_process_message(...)` | Telegram account-link + AI query workflow |

## Validation and error handling patterns
- Extensive `UserError`/`ValidationError` guards for required IDs/status checks before external writes.
- Access checks at service entry (`_ensure_system_access`, cashier group checks).
- Idempotency pattern using `pos_client_token` unique constraint (`ab_sales_header`).
- For external calls: explicit network exception handling and status-based failures.

## Known error cases
- Missing integration config keys (for example WhatsApp token, ePlus DB settings) raises explicit `UserError`.
- Invalid invoice state transitions (`prepending/pending/saved`) are blocked.
- Missing/invalid store mapping or employee ePlus serial blocks sales/returns push.
