# Fixed asset workflow repairs

## Current changes before commit:
- Prevent malformed Telegram tokens or chat IDs from rolling back asset creation or movement submission; log only a sanitized configuration warning. Verify eight notification cases, four ORM workflow cases and Playwright creation/submission with a token containing spaces. The configured token is not changed.
- Make movement submission atomic, reject repeats, retain posted journal links, and prevent edits to submitted transfer lines.
- Validate selected source ownership, aggregate transferred quantities, reject negative inventory values, and reconcile inventory transfer amounts.
- Serialize depreciation and movements against the same asset so concurrent requests cannot duplicate depreciation or consume the same balance twice.
- Calculate remaining asset value from posted cost less remaining accumulated depreciation, including asset inventory accounts; exclude draft journals.
- Cap depreciation at cost, reject future acquisition dates, and allow explicit useful-life adjustments without reversing prior write-downs during ordinary depreciation.
- Clear cost and accumulated depreciation on disposal and correct partial-write-down valuation. Keep Scrap Value as an estimate; sale proceeds require a separate accounting transaction.
- Implement depreciation-date filters and align fixed-asset journal filtering with its computed flag.
- Align posted asset form editability with backend restrictions, provide an Asset Movement action, require movement sources, and hide completed workflow buttons.
- Preserve Arabic translations, add matching ar/ar_001 strings for the changes, and repair an existing missing format placeholder.
- Validate with 42 backend checks, three concurrency scenarios, 17 Playwright checks, and runtime Arabic view/message checks in an isolated database. No historical transactions were repaired.

Files changed:
- models/ab_accounting_je.py
- models/ab_fixed_asset_assets_inventory.py
- models/ab_fixed_asset_inventory_line.py
- models/ab_fixed_asset_move_wizard.py
- views/ab_fixed_asset_assets_inventory.xml
- views/ab_fixed_asset_move_wizard.xml
- i18n/ar.po
- i18n/ar_001.po
- changelog.d/2026-11-15-workflow-safety.md

## fc6aae0d7f3df315c3f431e2800c1bf5ef4a41a2
Author: hossam elsheikh
Date: 2026-11-12
Subject: ab_fixed_asset/FIX: repair asset forms and contain table scrolling

- Repair asset and movement form layouts and contain embedded table scrolling.

Files changed:
- views/ab_fixed_asset_assets_inventory.xml
- views/ab_fixed_asset_move_wizard.xml
