# Legacy customer activation

Legacy customer code management is included in `ab_website_sale_product`. The existing `ab_ecommerce_storefront` handles account verification and the returning-customer welcome. No separate addon is required. The feature does not send messages or create, import, or modify loyalty points.

## Staff workflow

Open the existing **Eplus Stock** screen and select **Legacy Customer Codes**, the fourth always-visible toolbar button after **Sync to Odoo Inventory**. The button is available to Website Editors and Designers and System Administrators. It opens the list of activation batches without running any stock refresh or inventory synchronization.

1. Create a batch, select its website, upload the customer CSV, select its encoding if needed, and choose the expiry. The default is 30 days; the maximum is 90 days from preparation/generation. Expiry starts from the selected timestamp, not the SMS delivery date.
2. Select **Preview Customers** to validate and stage the eligible records. The preview reports valid candidates, excluded and inactive records, safe corrections, and column-level issues; no activation codes exist yet. Use **Review All Issues** to filter or group the report by column, reason, or import status.
3. Select **Create Customer Codes** and leave the page open. Processing uses transactions of at most 1,000 customers. If interrupted, reopen the same batch and select the button again to resume without rotating existing codes.
4. Select **Download SMS File** and securely give it to the external SMS provider. It contains `customer_reference`, `mobile_phone`, `activation_code`, `expires_at_utc`, and `message`. Message language follows the exporting user's language. Preserve phone values and leading zeros in codes as text. The provider must map these columns to its own import format.
5. **Cancel and Invalidate Unused Codes** invalidates remaining codes and removes the batch's encrypted export material. Completed customer links remain intact.

A repeated download contains the original batch's codes, including codes already redeemed since generation. It is not an automatic resend queue. Re-importing an existing reference or phone skips it, including expired or cancelled records; this version deliberately does not replace existing codes or relink an account.

## Input format

Required columns are `mobile_phone` and at least one stable identifier: `source_id`, `eplus_serial`, `code`, or `id`, in that priority order. Optional columns include `name`, `active`, and `default_store_id`. Imported identifiers remain external references and never become Odoo database IDs. The default source namespace is `eplus`; keep it consistent across imports.

Only valid Egyptian mobile numbers from `mobile_phone` are eligible. Work and delivery numbers are not used as fallback identifiers. Inactive rows are excluded. All occurrences of duplicate active identifiers or mobile numbers in the file are excluded to avoid assigning a shared number to the wrong customer. Existing references and phones on the selected website are skipped during generation.

Uploads use private Odoo attachment storage. Preview reads the CSV sequentially in two passes, counts duplicates across the complete file, and stages at most 10 chunks of 1,000 customers per ORM create call. Diagnostics are saved in bounded groups with their ORM caches flushed and invalidated. It does not load the full decoded CSV or all normalized customer dictionaries at once. The original upload remains available during review and processing, and is removed on completion or cancellation.

### Review table and supported variations

Every diagnostic identifies the source record, first/last physical file line, column name/number, original value, normalized value when applicable, reason, and import status. Several entries can describe different problems in one record. Clean records appear in the counts without creating unnecessary report rows. Record 0 describes the file/header. Values in the report are limited to 1,000 characters; use the retained upload for complete source values.

The reader detects comma, semicolon, tab, and pipe delimiters from the header. Header whitespace and letter case are normalized. UTF-8 (with or without BOM) and UTF-16 with BOM are detected automatically; Windows Arabic CP1256 requires explicit selection. Valid quoted multiline values and embedded delimiters are supported.

Safe corrections are visible: whitespace cleanup, Arabic/Persian phone digits, unambiguous missing Egyptian mobile leading zeros or Excel `.0` suffixes, extra empty trailing columns, fallback names, and shortening names to 200 characters. Stable customer references are never converted from floating-point or scientific notation.

Validation covers missing/duplicate headers; invalid encoding/control characters; malformed quotation marks; wrong column counts; empty/missing/invalid/scientific-notation phones; missing/invalid references; invalid active flags; field/store limits; inactive customers; duplicate active references/phones across the file; and existing website customers. Unused source columns are explicitly listed as information. This validates the activation input, not the business semantics of unused legacy columns.

Known record boundaries allow invalid rows to be excluded while valid candidates are staged. Ambiguous quoting or header errors put the entire batch in **Review Required**, retain all diagnostics, and stage no import chunks. Subsequent potential record boundaries are used only to continue diagnostics; they are never trusted for import while the file is blocked. Correct the original export rather than silently realigning damaged customer data.

Limits remain 90 MiB and 600,000 records, with 4,096 characters per field. A record exceeding 131,072 characters or 32 physical lines stops scanning and reports explicitly that the remainder was not scanned. Oversized uploads are rejected before ORM storage.

Use **Replace File / Review Again** before processing to clear derived diagnostics/chunks and return to draft, then upload a corrected file or select the right encoding. Review entries are read-only and cannot be edited to bypass validation. Once processing starts, this reset is unavailable. Existing customers are reported during preview and rechecked during generation; successful corrected rows become **Imported**, and existing customers become **Already Exists**.

The supplied `ab_store` file was scanned read-only and previewed in an isolated, rolled-back validation transaction. The new scanner reported 476,969 records and 258 quoting problems rather than stopping at the first broken name. Full preview produced 167,591 diagnostic entries, 343,371 structurally valid unique candidates, 88,310 excluded records, and 45,288 inactive records. These are diagnostic counts from a malformed file, not proof of the original export's intended customer count. The file remains blocked until its ambiguous quoting is corrected. No real customers or activation codes were imported/generated.

## Customer workflow

After login, a portal account with an already verified matching phone sees an activation prompt. An email-only account can use the activation link in its account page and enter its mobile number plus the SMS code. Email signup/login remains without OTP; this is a separate returning-customer activation step.

A successful claim links the authenticated account to one historical customer on that website and displays the returning-customer welcome message on subsequent visits. A match alone never grants the returning-customer status. Codes are 12 digits, single-use, expire at the batch timestamp, and stop accepting attempts after five failed submissions. IP and account rate limits also apply. This does not set the phone as a login/recovery identity or transfer historical account access.

## Access and storage

Staff can operate only their own batches in allowed companies; System Administrators can manage other owners' batches within their allowed companies. Column diagnostics follow the same owner/company restriction, including direct ORM/RPC access. Designers and administrators can read permitted diagnostics but cannot create, edit, or delete them directly. Public and portal users cannot read batches, column diagnostics, customer records, processing chunks, code digests, or export files through ORM/RPC. Exports check permissions server-side and create an audit row for the downloading user.

Verification uses a keyed digest; downloadable code material is encrypted using the product module's legacy activation security helper. Keep the Odoo database secret stable and protected. Claim and batch operations use shared transaction locks from that helper to prevent double claims or concurrent duplicate imports. Website/company boundaries apply to matching and claims.

## Validation and packaging

Development integration tests are in `ab_ecommerce_storefront/tests/test_legacy_activation.py`. They cover the fourth stock-toolbar button, batch processing, activation, export access, and Arabic display. Backend models, security, exports, and encryption have no dependency on the storefront; storefront account integration extends the base customer model. Run the two `TestLegacyActivation` and `TestLegacyActivationHTTP` classes against a dedicated, neutralized Odoo database with matching dependencies, installed `ar_001`, isolated HTTP/gevent ports, and cron disabled. The browser test clears generated asset attachments only inside its rolled-back test transaction so cloned databases can rebuild assets.

Production packages must exclude `tests/`, `__pycache__/`, compiled Python files, development fixtures, and local evidence. This feature adds no hooks, migrations, scheduled jobs, demo data, external database writes, or SMS integrations. Apply targeted upgrades to `ab_website_sale_product` and `ab_ecommerce_storefront`; never install the former separate `ab_ecommerce_legacy_customer` addon. Export requires HTTPS; isolated loopback testing can explicitly enable `ab_website_sale_product.development`.
