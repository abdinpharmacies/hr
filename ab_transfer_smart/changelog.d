Current changes before commit:

- Require an exact full store-code match in Fair Store quick search while retaining partial Arabic/name matching.
- Prevent a partial code such as 17 from matching store code 176.
- Keep the scoped Fair Store selectors, popup columns, and Select workflow unchanged.

Files changed:

- ab_transfer_smart/changelog.d
- ab_transfer_smart/views/ab_store_views.xml


commit caabf8b3452c922f76ff223d94571b72c3d023e5
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date:   Thu Aug 13 14:19:41 2026 +0300

    ab_transfer_smart/Refactor: Edit smart days to be 45

- Change the default Smart Days value from 60 to 45.

Files changed:

- ab_transfer_smart/models/ab_transfer_smart_wizard.py


commit 13fd68c0b9cae8aa8a90f642c12f878996118eb1
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date:   Thu Aug 13 14:00:50 2026 +0300

    ab_transfer_smart/Feat: search Fair Stores by name or code

- Add Fair Store quick search by store name or full/partial store code in the Smart Transfer wizard and header selectors.
- Scope the dedicated search view to Fair Store selectors so other Store searches keep their existing behavior.
- Keep the Fair Store popup columns and normal selection workflow unchanged.

Files changed:

- ab_transfer_smart/__manifest__.py
- ab_transfer_smart/changelog.d
- ab_transfer_smart/views/ab_store_views.xml
- ab_transfer_smart/views/ab_transfer_header_views.xml
- ab_transfer_smart/views/ab_transfer_smart_wizard_views.xml


commit 3cbd98ea89bdd74f46d1a3fa6dfaac01a233518e
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Wed Aug 12 13:45:21 2026 +0300

    ab_transfer_smart/fix: add pending concept in stock_qty to be stock_qty = on-hand + pending

- Include suspended incoming E-Plus transfer quantities in Smart Transfer destination stock cache totals.
- Add Pending Stock Quantity on destination stock cache rows to show the suspended incoming component separately.
- Merge converted on-hand destination stock with converted pending incoming stock during destination cache refresh.
- Keep generation logic unchanged so Smart Transfer need calculation continues subtracting stock_qty as the total destination stock.
- Show Pending Stock Quantity in the Smart Stock Cache list and form views.
- Add Arabic translations for Pending Stock Quantity.
- Add tests for pending stock SQL, on-hand plus pending cache totals, pending-only cache rows, and required quantity calculation.

Files changed:

- ab_transfer_smart/changelog.d
- ab_transfer_smart/i18n/ar.po
- ab_transfer_smart/i18n/ar_001.po
- ab_transfer_smart/models/ab_transfer_smart_cache.py
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_smart_cache_views.xml


commit b2499da5b6c02e12c39fe58d04e688d257df22e5
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Wed Aug 12 12:03:12 2026 +0300

    ab_transfer_smart/fix: convert destination stock cache quantities using E-Plus method not row

- Convert Smart Transfer destination stock cache quantities from E-Plus small-unit stock to the same UoM basis used by source stock and sales.
- Join destination stock cache SQL with item_catalog and divide Item_Class_Store.itm_qty by item_catalog.itm_unit1_unit3.
- Keep source stock, sales queries, destination cache schema, and generation flow unchanged.
- Add tests for converted destination cache output and required quantity calculation from converted destination stock.

Files changed:

- ab_transfer_smart/changelog.d
- ab_transfer_smart/models/ab_transfer_smart_cache.py
- ab_transfer_smart/tests/test_smart_transfer.py


commit 4911fe7db01475969681ca138ba91f58d1a75e9a
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Aug 11 18:29:03 2026 +0300

    ab_transfer_smart/ UPD remove redundent message to continue

- Remove the redundant Smart Transfer continuation message.
- Keep the related Smart Transfer flow covered by focused tests.

Files changed:

- ab_transfer_smart/changelog.d
- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/tests/test_smart_transfer.py


commit 9a64e5800b5b28a5122394e7ece6b50f7d5055bb
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Aug 11 18:07:45 2026 +0300

    ab_transfer_smart/ FIX huge eplus connections

- Add a Smart Transfer source opening-stock cache with one positive-stock row per source store, product, and cache day.
- Keep older source cache days available for analysis while forced refreshes replace only the current day.
- Use the source opening cache for wizard/header zero-stock checks and smart planning instead of live per-product source inventory reads.
- Show the zero-source-stock blocking popup only for explicitly selected/requested products; broad automatic generation now skips zero-stock products without the extra popup.
- Defer live class, batch, and expiry source inventory reads until pre-submit/submit/export paths that actually need transfer-line source details.
- Serialize source cache refreshes per source store and re-check after the refresh lock so concurrent users share one opening snapshot.
- Expose the source stock cache report menu with read access for Smart Transfer roles and full system access.
- Add Arabic translations and focused tests for source cache history, positive-row filtering, concurrency re-checks, product linking, planning without expiry/class, wizard source-cache ordering, and non-blocking broad zero-stock generation.

Files changed:

- ab_transfer_smart/i18n/ar.po
- ab_transfer_smart/i18n/ar_001.po
- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/models/ab_transfer_smart_cache.py
- ab_transfer_smart/models/ab_transfer_smart_line.py
- ab_transfer_smart/models/ab_transfer_smart_wizard.py
- ab_transfer_smart/security/ir.model.access.csv
- ab_transfer_smart/security/record_rules.xml
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_smart_cache_views.xml

commit b6899c66138c1be7dc21c4d35926b048943585d2
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Mon Aug 10 15:12:28 2026 +0300

    ab_transfer_smart/fix: use last version of pdf and use Portrait in pdf

- Align Smart Lines and Transfer Lines PDF reports with the requested compact portrait layout.
- Print B-Connect transfer numbers through Odoo locale-aware field formatting.
- Update report assertions for portrait orientation and compact printed columns.

Files changed:

- ab_transfer_smart/report/ab_transfer_line_reports.xml
- ab_transfer_smart/tests/test_smart_transfer.py


commit 0be5922230f594337903a1e90a15067eecc14f89
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Mon Aug 10 13:54:25 2026 +0300

    ab_transfer_smart/feat: persist B-Connect serial in Sent Lines report

- Add EPlus serial storage for Smart Transfer headers.
- Sync the B-Connect transfer serial after smart submit.
- Print the B-Connect transfer number in the Sent Lines report.

Files changed:

- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/report/ab_transfer_line_reports.xml


commit 36794b0a8be6ac9af2608e2ba773415e23851a9b
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Sun Aug 9 11:57:38 2026 +0300

     ab_transfer_smart/fix: Arabic translations and report labels

- Add Arabic translation file support for Smart Transfer.
- Improve Arabic translations for Smart Transfer labels and report strings.
- Translate printed report UOM values through Odoo translation context.
- Keep report and product-view source labels in English for dynamic language switching.

Files changed:

- ab_transfer_smart/i18n/ar.po
- ab_transfer_smart/i18n/ar_001.po
- ab_transfer_smart/report/ab_transfer_line_reports.xml
- ab_transfer_smart/views/ab_product_views.xml


commit 1c6a1d486a0aa6a4961aecb6235ea7c1a4ff4370
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Sun Aug 9 11:53:52 2026 +0300

    ab_transfer_smart/fix: limit Expected Stock reservations to current business day

- Deduct only current-day Smart Transfer reservations from Expected Stock.
- Include Submit-stage and submitted Smart Transfer lines created today in Expected Stock reservations.
- Keep Purchase Preparation, excluded smart lines, and excluded headers out of Expected Stock reservations.
- Add tests for today's active reservation stages and yesterday's ignored reservations.

Files changed:

- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/tests/test_smart_transfer.py


commit 0603c2d3f5d2f264138c9c6ead45348363db37cd (origin/pos19)
Author: hager yasser <hageryasser2002@gmail.com>
Date:   Sun Aug 9 09:57:25 2026 +0300

    ab_transfer_smart/Add scrollable 1000-line product input with paste limit

- Add a scrollable requested-products paste input for Smart Transfer.
- Limit pasted Smart Transfer product input to 1000 lines/products.
- Add a module-scoped JS field asset for the Smart Wizard product input.
- Add Smart Wizard styling for the large product input area.
- Update Smart Wizard and product views to support the requested-products workflow.

Files changed:

- ab_transfer_smart/__manifest__.py
- ab_transfer_smart/models/ab_transfer_smart_wizard.py
- ab_transfer_smart/static/src/js/smart_product_import_text_field.js
- ab_transfer_smart/static/src/scss/smart_header.scss
- ab_transfer_smart/views/ab_product_views.xml
- ab_transfer_smart/views/ab_transfer_smart_wizard_views.xml


commit ac03ac0e65ea25ee2078d64ea5f893f54e1b34f8
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Thu Aug 6 13:02:07 2026 +0300

    ab_transfer_smart/chore: remove add excel sheet

- Remove Excel file import from the Smart Transfer wizard.
- Remove Excel upload fields and backend parsing logic from Smart Wizard.
- Remove the custom Excel upload label template.
- Remove Excel import tests that no longer apply.
- Keep manual product entry available through the Smart Wizard form.

Files changed:

- ab_transfer_smart/__manifest__.py
- ab_transfer_smart/models/ab_transfer_smart_wizard.py
- ab_transfer_smart/static/src/xml/binary_upload.xml
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_smart_wizard_views.xml


commit af30b708a55979c02c944d315338a03a0cdfa825
Author: emadco88 <emadco88@gmail.com>
Date:   Wed Aug 5 16:47:26 2026 +0300

    ab_transfer_smart/ FIX ab_transfer_smart_product_line security delete

- Fix delete access configuration for Smart Transfer requested product lines.

Files changed:

- ab_transfer_smart/security/ir.model.access.csv


commit 2bb3c8f29e2e44a06b6762ef94b2fa13975b0efe
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date:   Wed Aug 5 14:51:25 2026 +0300

    ab_transfer_smart/duplicates plan.md initial setup

- Add the duplicate transfer detection and prevention plan document.
- Add duplicate checking support for Smart Transfer lines.
- Track Smart Transfer source type and creation day for duplicate validation.
- Validate duplicates when moving transfer headers out of Purchase Preparation.
- Add tests for duplicate prevention behavior.
- Update transfer views to expose duplicate-related smart line fields.

Files changed:

- ab_transfer_smart/dupliactes-detection-prevention-plan.md
- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/models/ab_transfer_smart_line.py
- ab_transfer_smart/models/ab_transfer_smart_wizard.py
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_header_views.xml


commit 865cdfa0dbe1fcc66e6dca0b9d0797dac7507818
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Aug 4 18:45:55 2026 +0300

    ab_transfer_smart/ UPD aggregate all offended smart lines

- Aggregate all offending Smart Transfer lines into one validation message.
- Improve validation feedback so users can fix multiple quantity issues together.
- Update Smart Transfer tests for aggregated validation output.
- Adjust transfer view support for the updated validation fields.

Files changed:

- ab_transfer_smart/models/ab_transfer_smart_line.py
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_header_views.xml


commit 9c486f16c4c4abb7da2d26e2a1b7aff8a24b1294
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Aug 4 18:25:07 2026 +0300

    ab_transfer_smart/ FIX ab_transfer_smart_product_line logic

- Fix Smart Transfer requested product line quantity logic.
- Keep computed need statistics separate from manual requested quantities.
- Update Smart Transfer line calculations and validation tests.
- Adjust transfer header view fields for the corrected requested-product workflow.

Files changed:

- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/models/ab_transfer_smart_line.py
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_header_views.xml


commit ddd728abe3e25ff503fc7dd743b58c1a0ff9e6ac
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Aug 4 17:58:02 2026 +0300

    ab_transfer_smart/ UPD add over_need qty as reference with conditional formatting

- Add Over Need quantity as a reference value on Smart Transfer lines.
- Add conditional formatting support for over-need quantity checks.
- Update transfer views to show the new over-need reference.
- Add test coverage for over-need behavior.

Files changed:

- ab_transfer_smart/models/ab_transfer_line.py
- ab_transfer_smart/models/ab_transfer_smart_line.py
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_header_views.xml


commit cb295fb1290aa66f9b7ec1cef563ccab39a1e3e1
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Aug 4 17:45:48 2026 +0300

    ab_transfer_smart/ UPD allow any qty in purchase prep stage

- Allow Smart Transfer quantities to be edited freely during Purchase Preparation.
- Keep stricter quantity validation for later workflow stages.
- Update tests for Purchase Preparation quantity editing behavior.

Files changed:

- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/models/ab_transfer_smart_line.py
- ab_transfer_smart/tests/test_smart_transfer.py
