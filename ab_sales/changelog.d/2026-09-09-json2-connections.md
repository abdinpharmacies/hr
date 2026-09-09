Commit: 04ead10b2aefe53d014ccdfb54b36f23b853fe86
Author: Hossam Elsheikh
Date: 2026-09-08 14:20:11 +0300
Subject: ab_sales/feat: route callcenter sales and returns through branch API

User-facing changes:
- Route callcenter stock, sales, and returns through branch Odoo with stable identifiers, request tokens, readable errors, and setup documentation.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/security/ir.model.access.csv
- ab_sales/views/ab_sales_branch_api_views.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-09-07-branch-api-client.md

Current changes before commit:

Author: Hossam Elsheikh
Date: 2026-09-09

- Replace outbound XML-RPC/password authentication with JSON-2 bearer requests and named arguments. Require explicit credential enrollment for existing configurations.
- Add central branch connection status, encrypted active/pending/previous credentials, responsible administrators, expiry, and rotation state. Block credential exports and restrict secret fields.
- Add bulk background checks, 15-minute health scheduling, daily rotation eligibility, 90-day key lifetime, rotation with 30 days remaining, and verified minimum 24-hour overlap.
- Persist rotation stages across remote transactions; serialize management and revocation, cap jobs at four concurrent executions, retain working keys on failed verification, and block repeated uncertain generation.
- Reuse the installed integration_queue_job implementation; the separate queue_job addon conflicts with its root channel and is not a dependency.
- Add deduplicated administrator activities, explicit revocation, sanitized errors, HTTPS enforcement, and preserved Arabic branch validation messages.
- Document enrollment, runtime configuration, safe recovery, business flows, JSON-2 interfaces, and deployment automation guidance. Release version 19.0.2.0.0.

Validation:
- Targeted ab_sales upgrade completed on callcenter19 after correcting the queue dependency.
- Odoo-registry tests passed for named transport requests, enrollment, readable Arabic errors, rotation, retirement, interruption handling, HTTPS validation, and secret export protection; 60 destinations exercised with mocked requests.
- Native branch JSON-2 authentication checked separately over HTTP. No sale or return posted to E-Plus.
- Restricted actions and secret fields, failed replacement verification, translated activity deduplication, four concurrent job slots, and rotation/revocation locking passed runtime tests.
- Both Arabic PO files checked against exported POT entries and validated with msgfmt; the connection action differs between en_US and ar_001 at runtime.

Deployment:
- Restart both Odoo processes and enroll branch credentials before use. XML-RPC credentials are not reused.
- Load integration_queue_job as the callcenter server-wide queue runner and configure root.branch_connections capacity; see BRANCH_API_WORKFLOW.md.
- Existing business request tokens and E-Plus reconciliation safeguards remain unchanged.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/views/ab_sales_branch_rpc_config_views.xml
- ab_sales/data/branch_connection_jobs.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-09-07-branch-api-client.md
- ab_sales/changelog.d/2026-09-09-json2-connections.md
