## c20d7abf - hager yasser - 2026-09-22

Original commit subject: ab_sales_promo_report/FEAT(#20092): Add a Dedicated Sales Promo Reports Access Group

- Add Sales Promo Reports under Abdin Sales, implying Internal User; system administrators inherit the new group automatically.
- Require explicit report-group assignment for Marketing users to load reports and manage their own report lines.
- Restrict both report menus and the report-line/wizard ACLs to the dedicated group while retaining administrator ACLs.
- Replace the ownership rule's Internal User group with the report group, preserving own-record isolation.
- Load the group definition before ACLs and record rules.
- Add Sales Promo Reports (تقارير العروض) and both menu translations in ar.po and ar_001.po using references exported from Odoo.
- Keep report calculations, sales data, and inventory logic unchanged.

Files changed:
- ab_sales_promo_report/__manifest__.py
- ab_sales_promo_report/security/security_groups.xml
- ab_sales_promo_report/security/ir.model.access.csv
- ab_sales_promo_report/security/record_rules.xml
- ab_sales_promo_report/views/menus.xml
- ab_sales_promo_report/i18n/ar.po
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/changelog.d

Validation:
- Targeted ab_sales_promo_report upgrade on abdin_replica(POS); all 25 existing tests passed (27 Odoo test-stat entries).
- Rollback-only XML user fixtures verified both menus, report loading, and own-line read/write/unlink for report users, plus administrator access.
- Marketing-only users were denied menus, direct model reads, and direct report loading; other-user lines were hidden and direct read/write/unlink denied.
- External report data was mocked; temporary users and report lines were rolled back.
- Both translation files passed msgfmt --check-format.
- Verified ar_001 runtime names differ from en_US for the group and both menus; the group displays تقارير العروض.
- Retried the translation upgrade successfully after a concurrent database update conflict; unrelated missing-module warnings remain in the replica environment.

Current changes before commit:

- Fetch complete invoice baskets within the existing date/store/source filters; apply the wizard product selection only when emitting report rows.
- Include purchased trigger and reward products for validated specific-product offers, and all purchased in-scope products for other supported offers, preserving quantities, prices, and invoice-level amounts.
- Require completed existing-engine purchase conditions, strictly positive expected savings, and positive recorded compensation matching the existing Odoo/B-Connect tolerance. Cache results per invoice/promotion and retain first-successful per-product precedence.
- Reject candidates when condition validation fails or cannot run; prevent fallback calculation from bypassing that gate and exclude incentives.
- Generate matched in_date rows only. Hide the unmatched-lines option while retaining its ignored compatibility field, existing historical statuses, and normal requesting-user/date replacement behavior.
- Replace unmatched-output guidance with application-validation guidance and append both new English/Arabic pairs using the Odoo 19 POT export.

Files changed:

- ab_sales_promo_report/changelog.d
- ab_sales_promo_report/i18n/ar.po
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/views/ab_sales_promo_report_views.xml

Verification:

- Installed the report addon and completed a targeted ab_sales_promo_report upgrade in isolated database codex_applied_promo_report_20261015, with external connections blocked.
- Eighteen grouped rollback-only checks passed: trigger/reward participation, output-only product filtering, complete-input cached validation, missing conditions/rewards, zero/negative/mismatched compensation, tolerance boundaries, minimum quantities and UoM, split/mixed-price/fractional rows, leftover quantities, domains, overlap semantics, store/date isolation, precedence, failure handling, SQL batching, replacement, report-user access, and runtime Arabic guidance.
- Compared expected discounts against the pre-change report implementation using identical complete baskets. Nine existing helpers for batching, fetching, candidate/date selection, discount calculation, compensation, and output values remain structurally unchanged.
- Reviewed mocked representative invoices: a valid A+B offer emits both products with invoice discount 20; an incomplete marked offer emits no rows; a one-unit cheapest-product BOGO emits no rows.
- Preserve existing engine semantics when specific-product trigger/reward scopes overlap: a single shared unit may satisfy that engine's existing checks. No distinct-unit rule was added.
- Both PO catalogs pass msgfmt --check-format, preserve existing entries, and use references exported from Odoo 19. Revised guidance and the report action were verified in ar_001.
- Python/XML syntax and git diff whitespace checks passed. All verification fixtures were rolled back; scripts remain in /tmp outside addon packages. No sales/pricing/security changes, migrations, hooks, cron jobs, production updates, or external writes were introduced.

Application evidence remains an inference from completed conditions and matching recorded compensation; the source has no definitive promotion-application identifier. Existing saved report rows adopt this behavior when reloaded through normal replacement.
