## f9aaae6f707e21d813dce02b554c68d3f4b136a7

Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-10-29 17:05:55 +0300
Subject: ab_sales/fix: preserve selected customer identity in branch submissions

- Preserve the selected customer's E-Plus identity and invoice customer snapshots.

Files changed:
- ab_sales/changelog.d/2026-10-29-callcenter-customer-identity.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml

## Current changes before commit:

- Send the server-configured callcenter DB serial for new promotion submissions when the receiver supports source identity.
- Preserve ordinary sales and legacy branch behavior; ignore browser-supplied source identity.
- Allow confirmed rejected corrections to add missing origin in a new audited revision without changing quantities or promotion.
- Preserve frozen retries, existing origin, lost-response correction replay, and destination routing.
- Add the configuration error in English and both Arabic catalogs; document rollout prerequisites and increment the version to 19.0.4.1.22.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/local_bills.py
- ab_sales/models/bill_corrections.py
- ab_sales/doc/technical_branch_metadata.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-30-promotion-source-identity.md

Verification:
- Targeted ab_sales upgrade passed on disposable database codex_cc_promotion_20261030 with cron and HTTP disabled and external connections blocked.
- 23 focused source/payload/correction checks and 30 existing draft-recovery checks passed; test records were rolled back.
- Five receiver checks passed on the existing receiver test database: source-only eligibility, legacy rejection, store restriction, promotion binding, and caller authorization. All changes were rolled back and external connections blocked.
- Exported the module POT before appending the new translation; both catalogs passed msgfmt --check-format.
- The new validation error and a sales menu differ between en_US and ar_001 at runtime.
- Development scripts and logs remain under /tmp; no test scaffolding was added to the production addon.
- Live databases and services were not upgraded or restarted. Activation requires deploying the code, targeted ab_sales upgrade, and worker restart.
