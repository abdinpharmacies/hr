# Allow new selection values in passive reporting mirrors

## Summary

Convert 19 source-owned fields from Selection to Char in the reports19 checkout. Preserve source keys exactly so new source options can synchronize without a reporting-module release.

Use raw keys in reporting views, exports, and grouping, as requested. Keep field captions translated. Implement in ab_sales, ab_sales_lead, ab_employee_access_sales, ab_sales_contract, and ab_odoo_sync_mapping.

## Model and interface changes

| Model | Fields to convert |
|---|---|
| ab_sales_header | status, push_state |
| ab_sales_line | unavailable_reason, ab_contract_discount_source, ab_contract_copay_mode |
| ab_sales_return_header | status |
| ab_sales_per_day_sync_state | state |
| ab_product_rank | rank_scope |
| ab_printer | protocol, paper_size |
| ab_sales_lead | lead_type, state, source, lost_reason, contact_preference |
| ab_employee_access_sales_shift | state |
| ab_employee_access_sales_pos_session | state |
| ab_employee_access_sales_operation_log | operation_type, operation_status |

- Preserve field names, existing defaults, indexes, labels, copy behavior, and other applicable attributes. Remove selection-specific arguments; do not impose a new character limit.
- Store incoming keys without translating, normalizing, or replacing unknown values. Preserve existing missing-field and empty-value behavior.
- Field metadata changes from selection to char; consumers must no longer expect an options list. Payload field names and values remain unchanged.
- Keep source_operation, mapping types, upload queue statuses, identity states, and hardware approval states as selections. The sales-per-day state listed above is a source-owned reporting snapshot, so it is included.
- Leave Transfer, Smart Transfer, source POS/callcenter worktrees, and unrelated models unchanged.

- Keep customer, contract, and promotion master selections: these models are explicitly excluded from passive mirroring by _never_mirror_models. Keep related promotion report fields and locally calculated statuses unchanged.
- Remove Python readonly on the two contract snapshot fields so existing upload eligibility permits them; retain read-only reporting views and ACLs.
- Extend automatic mapping only for source selection to target char in mirror_sync mode on passive mirror models. Preserve all existing writable/stored-field checks and business-model behavior.

## Mapping, views, and packaging

- Retain the existing direct mapping path: it already passes scalar source values into target fields. Do not add runtime field mutation, automatic option creation, or global validation bypasses.
- Preserve existing mapping profiles, enabled/ignored settings, and branch/source identities. Confirm that automatic mapping accepts source metadata declaring selection when the destination is char.
- Display raw values through existing fields. Retain Char-compatible badges and existing decorations for known keys; unknown keys receive neutral styling.
- Keep existing key-based filters and grouping. Verify unknown values remain visible in unfiltered views and can be searched/grouped. Do not classify unknown values as an existing business status.
- Preserve read-only reporting views and access rules. Add no label fields, translation dictionaries, or frontend components.
- Preserve existing Arabic translation entries. If any user-facing captions must change, export the module POT and merge corresponding entries into both Arabic PO files; validate with msgfmt --check-format.
- Bump existing patch versions in changed modules and set ab_sales_contract to 19.0.1.0.1. Inspect relevant git show output and the final diff, then create/update each module’s changelog.d with commit references and an accurate current-changes section.

## Verification and acceptance

Use an isolated Odoo 19 reporting database and external test scripts; do not ship test fixtures inside production addons.
- Verify fresh installation and a targeted upgrade from the current field definitions. Compare record counts, IDs, branch identities, and stored field values before and after upgrade; no records or values may disappear.
- For all 19 fields, apply a known key and a previously undefined key through the real upload/apply path. Both must persist exactly.
- Test create, update, optional empty values, omitted fields, and relation placeholders. Existing defaults must retain their current behavior.
- Exercise both existing direct mappings and automatic mapping from source selection metadata.
- Replay a failed-selection example in isolation and verify successful application without duplicate mirror records.
- Test identical source record IDs in two branches and branch-user access isolation.
- Open affected lists/forms, search, group, and export unknown keys. Verify badges render and known-value filters still work.
- Verify local control selections still reject unsupported values.
- Check English and Arabic views: captions retain their translations while stored keys display identically.

## Delivery and rollout assumptions

- This is a reporting-side compatibility change, with no source workflow or external-database changes.
- Selection and Char use compatible varchar storage here; use normal targeted module upgrades. Add no migration files, hooks, direct SQL rewrites, or bulk data repair.
- Resolve the actual reporting config/database before runtime validation; the reporting config is /opt/odoo19/odoo19-reports.conf; use a separate disposable database for validation. Do not substitute a POS or callcenter database.
- Deliver the source changes and verification results first. Live deployment and bulk retry of existing failed uploads are outside this implementation scope.
- For a later deployment, take a reporting database backup and upgrade only the five changed installed modules. Once new keys are stored, reverting to restrictive selections requires a compatibility review.

## Implementation and validation — 2026-11-02

Implemented all 19 conversions, five manifest version updates, module changelogs, and passive Selection-to-Char automatic mapping support. The mapping check recognizes both ab_odoo_sync_passive_mirror_mixin and the older ab_sales_mirror_mixin used by Sales Per Day Sync State and Product Rank. Reporting XML and security remain unchanged; existing sales views disable editing. No user-facing captions were added or changed, and existing translations were preserved.

Validation used the isolated database codex_reports_char_20261102 with /opt/odoo19/odoo19-reports.conf and a separate /tmp data directory. The live reports database was not upgraded.

Passed:
- Fresh installation of all five changed modules and their dependencies.
- Targeted upgrade and preservation of all 19 seeded field values, record IDs, branch IDs, and source IDs created using the original Selection definitions.
- Real upload/apply tests for 14 fields outside Sales Lead: known and unknown keys, create/update, empty values, omitted fields, repeated application without duplicates, two branches sharing source IDs, and raw-key export.
- ORM acceptance of unknown keys for all five Sales Lead fields.
- Automatic mapping type/eligibility checks for all 19 fields; business-model and non-mirror type mismatches remain rejected.
- Existing disabled mappings stay disabled when mappings are reloaded; local apply-mode Selection rejects unsupported values.
- Python syntax, git diff whitespace validation, and msgfmt --check-format for both existing ab_sales Arabic catalogs.

Remaining validation limitations:
- Sales Lead lacks a pre-existing unique (db_serial, rec_id) constraint. The mapping profile validator rejects its mirror-sync profile, so end-to-end upload testing of its five fields is blocked. This implementation does not add that separate schema change or repair existing data.
- Branch-user access isolation, browser badge/group/search behavior, relation placeholders, and Arabic runtime UI were not exercised. Branch identity separation was tested, which does not establish user access isolation.
- External scripts and logs are retained at /tmp/reports-char-validation; they are not packaged in production addons.
