Current changes before commit:
- Omit the hidden active default from audit form saves so Save and Prepare and Open respect the server create allowlist.
- Keep Correction Of editable only before the first save, matching its creation-only server contract.
- Verify browser creation for managers/administrators, English and both Arabic locales, corrective drafts, security and archive restrictions; pass 43 core, 21 regression and six focused tests plus 72 view checks on a disposable database. Document the verified XML developer reload and targeted-update paths.

Files changed:
- ab_inventory_audit/views/audit.xml
- ab_inventory_audit/changelog.d
- ab_inventory_audit/VALIDATION.md

Commit: 2b92422764b458d77ee87d3765466094c89b1a93
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-11-02
Subject: ab_inventory_audit/Fix: complete coverage and counting workflows

- Complete frozen product coverage with explicit absence evidence and independently reviewed stock observations; prevent counter-driven scope extensions.
- Separate group counting revisions from session approval revisions; add version-2 incremental Excel imports, exact attempt fingerprints and actionable stale/import feedback.
- Validate cost centers before approval without journal creation; persist blocked allocation quantities and require documented resolution with fresh availability checks.
- Add stable group/accepted-attempt references, retained late/new-source history, coverage/observation/allocation panels, counting notes/unit/barcode fields and scoped RTL rendering.
- Use native aggregate balances and scoped movement boundaries; benchmark the same 1,001-group fixture and one million unrelated historical movements.
- Add read-only tax-reference access for financial audit roles after browser verification exposed a manager wizard-save failure; retain denied tax mutation.
- Keep movement history and attachments empty on unsaved audit forms so initial onchange does not validate an unselected branch; retain persisted-record company/branch checks and audit role restrictions.
- Fix assignments, discrepancy review and accounting configuration views in XML developer mode by preserving architecture-leading whitespace; retain all view semantics and workflow/security logic.
- Add central-server full and partial branch audits with nine persistent models and guarded transient workflows.
- Preserve count attempts and accepted boundaries using source membership and saved movement identities; support manual, barcode and revision-bound Excel counting.
- Add deterministic whole-unit allocation, reasoned overrides, approved source proposals and frozen cost, tax and conversion inputs.
- Post atomic idempotent inventory adjustments and mandatory separate balanced surplus/shortage journals through existing services.
- Enforce company, branch, assignment and financial visibility; protect audit-linked accounting, sources, attachments and immutable history against ORM/RPC changes.
- Add module-scoped fast counting, review/configuration menus, session movements/attachments and PDF/XLSX reports.
- Supply complete English/Arabic UI, version 19.0.1.0.0, developer metadata and documented validation/capacity boundaries.
- Validate the original 43-case ORM suite plus 21 regression executions (two overlap the original rollback tests), four races, three optional native integration scenarios, multilingual views/browser/PDF/XLSX, connector-free installation, targeted upgrades and both performance fixtures. Keep validation code and artifacts outside the production module.

Files changed:
- ab_inventory_audit/README.md
- ab_inventory_audit/VALIDATION.md
- ab_inventory_audit/REQUIREMENTS.md
- ab_inventory_audit/__init__.py
- ab_inventory_audit/__manifest__.py
- ab_inventory_audit/changelog.d
- ab_inventory_audit/i18n/ar.po
- ab_inventory_audit/i18n/ar_001.po
- ab_inventory_audit/models/__init__.py
- ab_inventory_audit/models/audit.py
- ab_inventory_audit/models/common.py
- ab_inventory_audit/models/config.py
- ab_inventory_audit/models/counting.py
- ab_inventory_audit/models/coverage.py
- ab_inventory_audit/models/integration.py
- ab_inventory_audit/report/__init__.py
- ab_inventory_audit/report/audit_report.py
- ab_inventory_audit/report/reports.xml
- ab_inventory_audit/security/ir.model.access.csv
- ab_inventory_audit/security/record_rules.xml
- ab_inventory_audit/security/security_groups.xml
- ab_inventory_audit/static/description/icon.png
- ab_inventory_audit/static/src/fast_count.js
- ab_inventory_audit/static/src/fast_count.xml
- ab_inventory_audit/views/audit.xml
- ab_inventory_audit/views/menus.xml
- ab_inventory_audit/wizard/__init__.py
- ab_inventory_audit/wizard/workflow.py
- ab_inventory_audit/wizard/workflow.xml
