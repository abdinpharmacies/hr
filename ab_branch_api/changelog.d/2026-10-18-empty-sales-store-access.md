## 39e1ea2b2bb915e7665422c7975cb6421f9923b5 — Alhassan Hossny — 2026-10-18

Original commit subject: ab_branch_api: fix module description rendering errors

User-facing changes:
- Provide an explicit module description and its Arabic translations.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-18-description-rendering.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po

## Current changes before commit:

- Permit otherwise authorized active sales stores when the authenticated replica's Allowed Sales Stores list is empty.
- Continue rejecting stores outside a populated list. Preserve authentication, unique active sales-store resolution, and caller read access.
- No RPC signature or translated-message changes.

Files changed:
- ab_branch_api/changelog.d/2026-10-18-empty-sales-store-access.md
- ab_branch_api/models/branch_api.py

Validation:
- Local read-only Odoo tests verify empty-list acceptance and populated-list rejection through _resolve_store under ordinary user permissions.
- No remote deployment or external database writes.
