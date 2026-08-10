Current changes before commit:

- Keep Print Smart Lines available in Pre-Submit, Submit, and submitted transfers.
- Redesign the Sent Lines report to match the compact Smart Lines report while keeping actual transfer lines as its data source.
- Print the B-Connect transfer number from eplus_serial and keep the sent-line exclusion column empty.
- Keep Smart report ordering for sent lines and use the same compact paper format.
- Show Print Transfer Lines from Pre-Submit through Submit.
- Update Arabic report translations and add independent Smart/Sent report assertions.
- Add a read-only Smart Transfer XLSX preview to the draft Smart Transfer wizard.
- Match Generate Transfers by reading today's destination cache and using live destination SELECTs only when today's cache is absent.
- Export Smart calculation rows, including dropout exclusions, with code, company, minimum sale/purchase quantity, current Smart Line prices, stock, sales, weighted average, and final need.
- Add a stateless incomplete-sales-cache confirmation that can cancel or continue without recording acceptance.
- Show Smart Lines printing before Pre-Submit and Transfer Lines printing at Pre-Submit and Submit.
- Add Refresh Sales Cache & Resume beside Generated Transfers so missing daily sales cache is synced and generation resumes automatically.
- Keep the wizard blocked with the remaining missing-day warning when EPlus sales-cache refresh is incomplete.
- Keep the Excel warning popup from replacing the normal transfer form when opening generated transfers.
- Add a read-only wizard Excel preview with one worksheet per destination store and the approved fixed company name.
- Remove the duplicate transfer-header Excel action so the draft wizard is the single export entry point.
- Render a blank B-Connect transfer number safely in the pre-submit Sent Lines report when no EPlus serial field is available.
- Keep the Smart Lines and Transfer Lines PDF buttons bound to dedicated report sources: ab_transfer_smart_line and ab_transfer_line respectively.
- Add the product name immediately after the product code in the Smart Transfer Excel export.
- Print Product, Location, Quantity, Over Need, Expiry Date, UOM, Sell Price, Cost, and Purchase Price from ab_transfer_line in a landscape Transfer Lines PDF.
- Add Product Code to Transfer Lines and expand Smart Lines into a matching landscape detail report sourced from ab_transfer_smart_line.

Files changed:

- ab_transfer_smart/i18n/ar.po
- ab_transfer_smart/i18n/ar_001.po
- ab_transfer_smart/__init__.py
- ab_transfer_smart/__manifest__.py
- ab_transfer_smart/models/ab_transfer_header.py
- ab_transfer_smart/models/ab_transfer_smart_wizard.py
- ab_transfer_smart/report/__init__.py
- ab_transfer_smart/report/ab_transfer_smart_xlsx.py
- ab_transfer_smart/report/ab_transfer_smart_xlsx_report.xml
- ab_transfer_smart/report/ab_transfer_line_reports.xml
- ab_transfer_smart/tests/test_smart_transfer.py
- ab_transfer_smart/views/ab_transfer_header_views.xml
- ab_transfer_smart/views/ab_transfer_smart_wizard_views.xml


commit 36794b0a8be6ac9af2608e2ba773415e23851a9b (HEAD -> pos19)
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
