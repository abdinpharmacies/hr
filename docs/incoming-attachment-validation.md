# Incoming Telegram attachment repair — 2026-11-08

## Diagnosis and behavior

The original unsupported photo event retained no original provider attachment metadata, so its precise rejection cause cannot be recovered. The updated normalizer selects a downloadable photo variant, supports live-photo stills and assigns the image validation path to image documents. The user's new photo arrived as a ready JPEG (253446 bytes), and a static sticker arrived as a ready WebP (10030 bytes) after the first receiver reload. Neither new message used the unsupported fallback.

The old receiver had no sticker branch and rejected Markdown MIME types. Safe diagnostics subsequently identified two rejected animated stickers (`is_animated=true`, 7340 and 7285 bytes). These diagnoses are independent of the earlier location repair.

Gateway 1.2.1 normalizes static stickers as images, animated stickers as original TGS documents and video stickers as WebM documents. Markdown extensions `.md` and `.markdown` accept common text MIME aliases, including generic binary MIME metadata, but still require valid UTF-8 content without NUL bytes in Odoo. Markdown content is downloaded, never rendered as HTML. Animated TGS content is limited to one MiB after decompression and must contain a JSON object with a layers list. Animated TGS files are downloadable; inline TGS animation is not implemented. Existing WebM preview handles video stickers. Existing image and file size limits remain enforced.

Odoo `ab_crm_messaging` 19.0.1.5.1 applies validation to service ingestion and direct ORM/RPC workflow entry points, preserving service authorization, branch/company restrictions, immutable bytes and scoped downloads. No new fields or source UI strings were introduced. Both Arabic catalogs retain the existing translated validation and download controls.

## Verification

- Full gateway suite: **141 passed, 1 skipped**. The skip is the existing optional FFmpeg check. Log: `/tmp/image-runtime-fix/gateway-tests.log`.
- Isolated Odoo messaging upgrade: **26 test methods, zero failures/errors**, database `crm_location_messaging_test_20261108`, ports 5073/5074, no cron workers. Log: `/tmp/image-runtime-fix/odoo-tests.log`.
- Added coverage includes photo variants/missing size/live-photo stills, image documents, Markdown MIME aliases, static/animated/video stickers, private diagnostics, mocked worker downloads, invalid text, invalid or oversized compressed animation, foreign staff denial and immutable replacement denial.
- Downstream workspace and optional WhatsApp bridge: **85 test methods, zero failures/errors**, including 40 browser HOOT cases, database `crm_location_final_test_20261108`, ports 5069/5072. Log: `/tmp/image-runtime-fix/workspace-tests.log`. Temporary HTTP/gevent ports were released after shutdown.
- A preliminary combined run hit a base messaging fixture setup error because that fixture does not supply the installed workspace addon's required intake mapping. The base messaging suite passed in its separate base-only database; the downstream suites passed separately with workspace configuration. The failed combined run remains available in `/tmp/image-runtime-fix/downstream-tests.log`.
- Changed Python syntax and whitespace checks passed. Both Arabic catalogs were compared byte-for-byte with the attachment-task baseline; no changes were needed.

## Runtime and delivery

Consumer changes must be loaded before the updated receiver and worker emit/download the new formats. The user's PyCharm process owns callcenter port 4092; validation uses isolated databases and alternate ports. No provider sends are made by validation. Historical unsupported messages are unchanged; their discarded attachment metadata requires customers to resend after activation.

The user restarted Callcenter at 15:42:25 EET. After verifying Odoo availability and an idle outgoing queue, the receiver and worker were reloaded at 15:43:42 EET. Both services became active with the new source; the user's restarted Odoo process was preserved. No live database upgrade or historical message rewrite was performed for this Python-only repair.

At 15:45 EET, the user's two resent Markdown files (5447 and 491 bytes) and animated TGS sticker (8225 bytes) each completed on the first queue attempt. All three messages had `unsupported=false`; all three media records reached `ready`. Together with the earlier JPEG and WebP arrivals, this verifies the live provider-to-private-media path for every reported failing category. Video-sticker normalization and validation passed automated tests, but no live video sticker was supplied.

Source and runtime packages are generated under `/tmp/image-runtime-fix`. Runtime packages exclude development tests, caches and local credentials. The existing location feature and unrelated work remain preserved.
