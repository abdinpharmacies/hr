# 7. Configuration and Environment

## Runtime requirements
- Odoo 19 (repository is addons-only, not full server source).
- Python 3.10+ (project guidance states Python >=3.10).
- PostgreSQL for Odoo.
- MSSQL connectivity for ePlus integrations (via `pyodbc` or `pymssql`).

## Python libraries referenced by code
- `requests` (WhatsApp, WAN, queue-job internals)
- `telebot` (Telegram webhook/bot)
- `pyodbc` and/or `pymssql` (ePlus SQL)
- `cryptography` (password decryption in integration connectors)
- `pyzk` (`zk` import for fingerprint module)
- `paramiko` (auto backup to SFTP)
- `Pillow` (`PIL` for captcha and some printing paths)
- `python-escpos`, `imgkit`, `win32print` (printing-related flows; environment-dependent)

## Odoo config keys (`odoo.conf`) used by custom modules
| Key | Used by | Purpose |
|---|---|---|
| `db_serial` | `ab_store`, `ab_sales` | Select current `ab_replica_db` policy and generate idempotent serial keys. |
| `repl_db` | `ab_sales`, `ab_wan`, `ab_odoo_replication_upload` | Replica DB/store context for replication/upload and WAN update. |
| `bconnect_ip1`, `bconnect_ip2`, `bconnect_user`, `bconnect_db` | `ab_eplus_connect` and ePlus replication modules | Main/secondary MSSQL host and DB credentials. |
| `decryption_key` | `ab_eplus_connect`, `ab_odoo_connect` | Decrypt encrypted DB/server passwords. |
| `xmlrpc_pass` | `ab_base_models_inherit`, `ab_odoo_replication` | Protect remote password retrieval and some replication operations. |
| `is_control_server` | `ab_odoo_replication/models_inherit` | Allows local promo CRUD on control server only. |
| `openai_api_token` / `openai_api_key` | `ab_user_extra` | Telegram AI integration auth. |
| `openai_base_url`, `openai_model` | `ab_user_extra` | AI endpoint and preferred model. |
| `whatsapp_token`, `whatsapp_phone_number_id`, `whatsapp_business_account_id`, `whatsapp_verify_token`, `whatsapp_api_version` | `ab_whatsapp_api` | WhatsApp Cloud API send/sync/webhook verification. |

## `ir.config_parameter` keys used by custom modules
| Key | Module | Purpose |
|---|---|---|
| `bconnect_crypt_pass` | `ab_eplus_connect` | Encrypted MSSQL password source. |
| `server_address`, `server_db`, `server_user`, `server_password` | `ab_odoo_connect` | Remote Odoo XML-RPC connection params. |
| `telebot_api_key`, `telebot_webhook_url` | `ab_telegram_webhook`, `abdin_telegram` | Telegram bot token and webhook URL override. |
| `ab_telegram_webhook.echo_start_ts` | `ab_telegram_webhook` | Ignore stale Telegram messages before setup time. |
| `mssql.server`, `mssql.database`, `mssql.username`, `mssql.password`, `mssql.driver`, `mssql.import_policy` | `ab_hr_applicant` | Applicant MSSQL import connection/policy settings. |
| `ab_sales.cashier_poll_min_seconds`, `ab_sales.cashier_poll_max_seconds` | `ab_sales_cashier` | Cashier polling range. |
| `ab_sales.pos_*` printer/settings keys | `ab_sales_ui_api` | POS printer and UI setting persistence. |
| `web.base.url` | multiple modules | Builds links and webhook defaults. |

## Third-party services and systems
- **ePlus MSSQL**: primary transactional integration target.
- **Control Odoo Server**: XML-RPC replication source/destination.
- **Telegram Bot API**: webhook and outbound messages.
- **Meta WhatsApp Cloud API**: templates, messages, media.
- **SFTP server** (optional): backup offloading in `auto_backup`.

## Scheduled jobs visible in repo
- Sales: balance refresh, pending-status sync, ranking refresh (`ab_sales/data/ir_cron.xml`).
- Replication: Odoo replication cron disabled by default (`ab_odoo_replication/views/cron_ab_odoo_replication.xml`).
- ePlus customer collect cron disabled by default (`ab_eplus_collect_customers/data/cron_ab_eplus_collect_customers.xml`).
- Offer replication cron disabled by default (`ab_offer_eplus_cycle/data/scheduled_actions.xml`).
- Fingerprint sync enabled (`ab_hr_fingerprint/data/download_data.xml`).
- Backup scheduler disabled by default (`auto_backup/data/backup_data.xml`).

---

# 8. Setup and Run

## Install
1. Prepare Odoo 19 environment (outside this repository).
2. Add this repository path to `addons_path`.
3. Install Python dependencies used by enabled modules.
4. Configure required `odoo.conf` keys and `ir.config_parameter` values.
5. Update app list and install required addons in dependency order.

### Example command patterns (exact paths are environment-specific)
```bash
# Linux example (adjust paths)
./odoo-bin -c /path/to/odoo.conf -d <db_name> -u base
./odoo-bin -c /path/to/odoo.conf -d <db_name> -i ab_store,ab_product,ab_customer,ab_sales
```

```powershell
# Windows example (adjust paths)
python .\odoo-bin -c .\config\odoo.conf -d <db_name> -i ab_store,ab_product,ab_customer,ab_sales
```

## Configure
Minimum practical startup set for sales integration:
- `ab_store`
- `ab_product`
- `ab_customer`
- `ab_eplus_connect`
- `ab_sales`

Then optional domains:
- Cashier: `ab_sales_cashier`
- Promotions/contracts: `ab_promo_program`, `ab_sales_promo`, `ab_sales_contract`
- HR stack: `ab_hr`, `ab_hr_effects`, `ab_hr_fingerprint`, `ab_hr_applicant`, `ab_hr_org_chart`
- Communications: `ab_telegram_webhook`, `ab_user_extra`, `ab_whatsapp_api`
- Replication: `ab_odoo_connect`, `ab_odoo_replication`, `ab_odoo_replication_upload`

## Run locally
- Start Odoo with this addons path included.
- Validate DB connectivity from Odoo to MSSQL before sales submission.
- Validate external webhooks only after public HTTPS endpoint setup.

## Testing
Tests exist for selected modules:
- `ab_distribution_store/tests/test_distribution_store.py`
- `ab_sales_cashier/tests/test_cashier_api.py`
- `ab_user_extra/tests/test_user_telegram_link.py`
- `ab_whatsapp_api/tests/test_ab_whatsapp_api.py`
- `ab_hr_org_chart/tests/test_employee_deletion.py`

Example pattern:
```bash
./odoo-bin -c /path/to/odoo.conf -d <db_name> --test-enable -i ab_sales_cashier --stop-after-init
```

## Build/deploy behavior visible from repo
- `ab_odoo_update` can run `git pull` and trigger a restart helper script.
- Root scripts include printer setup/bridge helpers (`print_receipt.py`, `thermal_slk_escpos.sh`, `thermal_slk_sewoo_official.sh`).

## Unclear from codebase
- Exact production systemd/supervisor service units.
- Canonical full dependency lockfile for all enabled addons.
- Official CI pipeline definitions.

---

# 9. Key Design Decisions

## 1) Direct ePlus SQL integration from business models
- Decision: Sales, returns, adjustments, and inventory use direct MSSQL queries.
- Why: Tight coupling with existing ePlus schema and performance.
- Tradeoff: Higher SQL maintenance burden and DB-specific logic in model layer.

## 2) Replica policy driven by `ab_replica_db` + `db_serial`
- Decision: Store permissions and return window are runtime-selected by config serial.
- Why: One codebase serving multiple replica databases with different branch policies.
- Tradeoff: Misconfigured `db_serial` can block flows or apply wrong policy.

## 3) Idempotency token in POS submit
- Decision: `pos_client_token` unique constraint on sales header.
- Why: Avoid duplicate invoice creation during retries/network errors.
- Tradeoff: Client must supply stable token per logical transaction.

## 4) Replication-protected master data
- Decision: Block manual CRUD on selected replicated models unless `context['replication']`.
- Why: Preserve control-server authority.
- Tradeoff: Local emergency edits are intentionally restricted.

## 5) Service-style transient APIs for UI actions
- Decision: Many OWL screens call transient model methods (`ab_sales_ui_api`, `ab_sales_cashier_api`, `ab.whatsapp.service`).
- Why: Keep UI behavior server-driven and reuse business logic.
- Tradeoff: Less explicit public API contract than dedicated REST schema.

---

# 10. Risks / Gaps / Technical Debt

## Confirmed risks from codebase
1. **Dependency mismatches in manifests**
- `ab_inventory_adjust` depends on `ab_eplus_replication` (not present in this repo).
- `ab_product_source` depends on `ab_taxes` (not present in this repo).
- `ab_transfer` depends on `ab_employee` (not present in this repo).

2. **Legacy JS module style still present**
- Multiple custom JS files still use `odoo.define(...)` (for example in `ab_inventory_adjust`, `abdin_js`, `ab_hr_org_chart`), while Odoo 19 guidance prefers ES modules.

3. **Deprecated constraint style still present**
- `ab_sales_contract/models/ab_contract_product_origin.py` uses `_sql_constraints` instead of `models.Constraint`.

4. **Raw SQL and low-level cursor usage in business code**
- Multiple modules use raw SQL and direct cursor access (`self._cr` or `env.cr.execute`) including transfer/inventory/sales paths.
- Increases maintenance and migration risk.

5. **XML-RPC dependence for replication**
- `ab_odoo_connect` + replication modules rely on XML-RPC; this is legacy-oriented architecture.

6. **Potential sensitive script artifact**
- `abdin_telegram/models/telebot_register_users.py` contains a hardcoded bot token and standalone polling script pattern.
- It is not imported by module `__init__`, but should still be treated as sensitive technical debt.

7. **Sparse automated test coverage relative to module count**
- Only a subset of custom modules have tests; many core flows (for example full sales push path) have no visible automated integration tests in-repo.

8. **Repository contains addons only**
- Full deployment/runbook and infra settings are outside this repo, increasing onboarding uncertainty.

## Documentation gaps
- No in-repo canonical architecture diagram.
- No unified config reference file for required keys per module.
- No consolidated dependency installation guide.

## Suggested additional docs (missing)
- `docs/config-reference.md`: all `odoo.conf` + `ir.config_parameter` keys by module.
- `docs/integration-eplus.md`: SQL tables touched, transaction boundaries, recovery playbook.
- `docs/security-model.md`: groups, privileges, record rules, and data access matrix.
- `docs/operations-runbook.md`: cron policy, monitoring, failure triage, restart strategy.
- `docs/testing-strategy.md`: test scope, gaps, and smoke-test checklist.
