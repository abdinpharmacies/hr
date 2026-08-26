Commit: ce0201fc77d14bec8772eb49e0f42181bafdb6cd
Author: emadco88 <emadco88@gmail.com>
Date: 2026-08-04 17:29:48 +0300
Subject: ab_sales/ UPD add only_default_sales_uom logic

User-facing changes:
- Added POS handling for products restricted to default sales UoM.
- Updated POS price badge behavior and product configuration view support.
- Added focused coverage for POS price badge behavior.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/tests/test_pos_price_badges.py
- ab_sales/views/ab_product_inherit.xml

Current changes before commit:
- Add Phase 1 branch Odoo XML-RPC configuration records for call-center routing preparation.
- Add encrypted RPC password/API key and optional sync-key storage using the existing Odoo `decryption_key` configuration.
- Add a read-only connection test that authenticates, checks remote read access, and verifies that the selected local store matches a remote `ab_store` by E-Plus serial or code.
- Add system-only access and configuration menu entries for branch RPC setup.
- Add Arabic translations for the new Phase 1 configuration surface.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-08-26-callcenter-branch-rpc-phase1.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/security/ir.model.access.csv
- ab_sales/views/ab_sales_branch_rpc_config_views.xml
