Commit: b6f8a3fbddf12f1d95f7794a575f1252ec86442c
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26 12:35:52 +0300
Subject: ab_sales/Implemented Phase 1 in ab_sales: per-branch Odoo XML-RPC configuration plus a read-only "Test Connection" action. No POS submit behavior was changed, and nothing creates invoices or writes to E-Plus yet.

User-facing changes:
- Added Phase 1 branch Odoo XML-RPC configuration records for call-center routing preparation.
- Added encrypted RPC password/API key and optional sync-key storage using the existing Odoo `decryption_key` configuration.
- Added a read-only connection test that authenticates, checks remote read access, and verifies that the selected local store matches a remote `ab_store` by E-Plus serial or code.
- Added system-only access and configuration menu entries for branch RPC setup.
- Added Arabic translations for the new Phase 1 configuration surface.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase1.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/security/ir.model.access.csv
- ab_sales/views/ab_sales_branch_rpc_config_views.xml

Current changes before commit:
- Fix the read-only branch connection test for Odoo 19 XML-RPC by avoiding a successful access-check result of `None`, which cannot be marshalled by the server XML-RPC controller.

Files changed:
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase1.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_rpc_config.py
