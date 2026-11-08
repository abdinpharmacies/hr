# Legacy customer activation

Legacy customer code management is included in `ab_website_sale_product`. The existing `ab_ecommerce_storefront` handles account verification and the returning-customer welcome. No separate addon is required. The feature does not send messages or create, import, or modify loyalty points.

## Staff workflow

Open the existing **Eplus Stock** screen and select **Legacy Customer Codes**, the fourth always-visible toolbar button after **Sync to Odoo Inventory**. The button is available to Website Editors and Designers and System Administrators. It opens the list of activation batches without running any stock refresh or inventory synchronization.

1. Create a batch, select its website, upload the customer CSV, select its encoding if needed, and choose the expiry. The default is 30 days; the maximum is 90 days from preparation/generation. Expiry starts from the selected timestamp, not the SMS delivery date.
2. Select **Preview Customers** to validate and stage the eligible records. The preview reports valid candidates, excluded and inactive records, safe corrections, and column-level issues; no activation codes exist yet. Use **Review All Issues** to filter or group the report by column, reason, or import status.
3. Select **Download Customer Review CSV** before generating codes. The CSV keeps the original column order and values, places eligible customers first, and appends translated status, problem/correction, machine-readable reason codes, corrected phone/name, stable customer reference, and source record/line numbers. Damaged records retain their original text in a separate column instead of guessing column alignment. Spreadsheet formula-like cells are prefixed with an apostrophe; import phone/reference/code columns as text. The report uses UTF-8 with BOM and bounded temporary files, and contains no activation codes.
4. Select **Create Customer Codes** and leave the page open. Processing uses transactions of at most 1,000 customers. If interrupted, reopen the same batch and select the button again to resume without rotating existing codes.
5. Select **Download SMS File** and securely give it to the external SMS provider. It contains `customer_reference`, `mobile_phone`, `activation_code`, `expires_at_utc`, and `message`. Message language follows the exporting user's language. Preserve phone values and leading zeros in codes as text. The provider must map these columns to its own import format.
6. **Cancel and Invalidate Unused Codes** invalidates remaining codes and removes the batch's encrypted export material. Completed customer links remain intact.

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

Malformed quoted records are quarantined without repairing their customer identities. Recovery requires a complete strictly parsed row, the expected column count, a stable reference in the first source column, a valid mobile, and a recognized active flag. Continuations that fail these checks remain excluded. Phones found in damaged records and available stable reference prefixes also participate in duplicate exclusion. Headers without a leading reference cannot safely recover broken quoting and still block generation. Header errors, decoding errors in headers, and incomplete scans also block generation; a blocked preview never stages customer chunks.

The screen shows **Eligible for New Codes**, **Existing Customers**, and **Eligible Percentage**. Eligibility excludes invalid/inactive records, duplicated identities, and references/phones already on the website. The denominator is all scanned records, including exclusions and inactive records; header/file notes are excluded. These are parser record counts, not a guarantee of the original exporter's intended customer count. A structurally blocked, cancelled, or outdated preview has zero eligible customers. Eligibility does not grant returning-customer status; the customer must still verify the activation code.

Limits remain 90 MiB and 600,000 records, with 4,096 characters per field. A record exceeding 131,072 characters or 32 physical lines stops scanning and reports explicitly that the remainder was not scanned. Oversized uploads are rejected before ORM storage.

Use **Recheck and Apply Safe Corrections** to refresh an existing unprocessed preview in one action, including previews created before the current validation rules. Use **Replace File / Review Again** before processing to clear derived diagnostics/chunks and return to draft, then upload a corrected file or select the right encoding. Review entries are read-only and cannot be edited to bypass validation. Once processing starts, this reset is unavailable. Existing customers are reported during preview and rechecked during generation; successful corrected rows become **Imported**, and existing customers become **Already Exists**.

The original source file is never overwritten. Preview and review download do not create customer accounts, activate returning-customer status, generate codes, send SMS, or change loyalty data. Code generation remains a separate explicit staff action. The review download is available for the current unprocessed preview; save it before generation completes and the source upload is removed.

## Customer workflow

After login, a portal account with an already verified matching phone sees an activation prompt. An email-only account can use the activation link in its account page and enter its mobile number plus the SMS code. Email signup/login remains without OTP; this is a separate returning-customer activation step.

A successful claim links the authenticated account to one historical customer on that website and displays the returning-customer welcome message on subsequent visits. A match alone never grants the returning-customer status. Codes are 12 digits, single-use, expire at the batch timestamp, and stop accepting attempts after five failed submissions. IP and account rate limits also apply. This does not set the phone as a login/recovery identity or transfer historical account access.

## Access and storage

Staff can operate only their own batches in allowed companies; System Administrators can manage other owners' batches within their allowed companies. Column diagnostics follow the same owner/company restriction, including direct ORM/RPC access. Designers and administrators can read permitted diagnostics but cannot create, edit, or delete them directly. Public and portal users cannot read batches, column diagnostics, customer records, processing chunks, code digests, or export files through ORM/RPC. Exports check permissions server-side and create an audit row for the downloading user.

Verification uses a keyed digest; downloadable code material is encrypted using the product module's legacy activation security helper. Keep the Odoo database secret stable and protected. Claim and batch operations use shared transaction locks from that helper to prevent double claims or concurrent duplicate imports. Website/company boundaries apply to matching and claims.

## Validation and packaging

Development integration tests are in `ab_ecommerce_storefront/tests/test_legacy_activation.py`. They cover the fourth stock-toolbar button, batch processing, activation, export access, and Arabic display. Backend models, security, exports, and encryption have no dependency on the storefront; storefront account integration extends the base customer model. Run the two `TestLegacyActivation` and `TestLegacyActivationHTTP` classes against a dedicated, neutralized Odoo database with matching dependencies, installed `ar_001`, isolated HTTP/gevent ports, and cron disabled. The browser test clears generated asset attachments only inside its rolled-back test transaction so cloned databases can rebuild assets.

Module-local HTTP regression tests are in `tests/test_legacy_review_download.py`. They cover review downloads without development mode, owner/company restrictions, administrator access, anonymous/portal rejection, outdated previews, and the separate HTTPS requirement for activation codes.

Production packages must exclude `tests/`, `__pycache__/`, compiled Python files, development fixtures, and local evidence. This feature adds no hooks, migrations, scheduled jobs, demo data, external database writes, or SMS integrations. Apply targeted upgrades to `ab_website_sale_product` and `ab_ecommerce_storefront`; never install the former separate `ab_ecommerce_legacy_customer` addon. Customer review downloads use the authenticated backend connection, including HTTP on local/demo environments, and enforce staff, owner, and company permissions. Activation-code exports require HTTPS; isolated loopback testing can explicitly enable `ab_website_sale_product.development` for those exports.
