Current changes before commit:
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
