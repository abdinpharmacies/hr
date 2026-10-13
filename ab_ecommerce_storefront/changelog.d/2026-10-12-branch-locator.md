# Interactive public branch directory

Current changes before commit:
- Add the native, published `/branches` website page for the existing footer link.
- Import the 42 branch names, addresses and exact Google Maps coordinates listed at https://www.abdinpharmacies.com/en_GB/store-locations on 2026-10-12. The directory spans nine governorates; the page count describes these listed locations rather than asserting the chain's total current branch count.
- Show a Leaflet map with the website's Abdin logo on branch markers and nearby marker groups. Serve pinned mapping libraries locally and retain their licenses and OpenStreetMap attribution.
- Open branch details on the physical right on desktop and in a native modal bottom sheet on mobile. Provide directions, the verified shared hotline 19036, deep links, keyboard dismissal, focus restoration and reduced-motion support.
- Add bilingual search, governorate filtering, map/list switching, empty states and a useful branch list when map assets fail. Location is requested only after the visitor chooses the nearest-branch control; distances are calculated locally and are not stored. The current HTTP LAN origin needs HTTPS for browser geolocation.
- Keep public directory content separate from operational branches, inventory and company records. No new models, security permissions, background jobs, external database access or business-data changes.
- Opening hours and branch-specific photos are absent from the source. Show a branded profile cover and advise confirming hours through the hotline. Image search did not establish reliable photos for individual locations.
- Add canonical Odoo-exported translation entries to both Arabic catalogs, preserving existing terms and unrelated changes.

Validation:
- Targeted `-u ab_ecommerce_storefront --stop-after-init` succeeded on the neutralized, dedicated `codex_ecom_branches_20261012` database with HTTP 5169/gevent 5172, workers 0 and cron 0. The active `ecom19` database was not modified.
- Public HTTP rendering succeeded in English and Arabic with 42 cards, translated branch names and addresses, and compiled frontend JS/LTR/RTL CSS assets.
- All 42 coordinates, source map links and rendered Arabic addresses match the supplied directory. All 95 exported page/JavaScript terms are translated in both catalogs; both pass `msgfmt --check-format`. All 11 JavaScript terms are present in the Arabic website translation response.
- 54 interaction assertions pass against rendered Odoo pages using JSDOM and the real Leaflet/markercluster libraries: filters, Arabic normalization, markers, selected profiles, directions, deep links, Escape, covered-list focus isolation, mobile modal behavior, nearby sorting, denied/insecure geolocation, map failure and cleanup.
- XML, manifest paths, SCSS compilation, JavaScript syntax and `git diff --check` pass. Compiled RTL CSS preserves the map's LTR grid placement and Arabic detail text direction.
- No graphical browser is connected to the available browser-control tool. Pixel-level visual review and real mobile touch interactions remain unverified; JSDOM does not measure layout or test native dialog focus trapping.
- The active development process was not stopped or restarted. Activating the new page/assets on port 4092 requires the normal targeted module upgrade and process reload. The owning module has substantial pre-existing worktree changes outside this task, so applying that whole module also activates unrelated edits.

Reproduce the interaction checks with JSDOM 26.1.0 installed outside the addon:

```bash
AB_JSDOM_PATH=/tmp/ab_branches_validation/node_modules/jsdom \
AB_BRANCH_FIXTURES=/tmp/ab_branches_validation \
node ab_ecommerce_storefront/tests/check_branches.cjs
```

The fixture directory contains public Odoo responses `ar.html`, `en.html`, and the Arabic PO mapping `ar_terms.json`. Keep `tests/` and generated verification outputs out of runtime packages.

Files changed:
- `__manifest__.py`
- `views/branches_data.xml`
- `views/branches_templates.xml`
- `static/src/js/branches.js`
- `static/src/scss/branches.scss`
- `static/lib/README.md`, `static/lib/leaflet/`, `static/lib/leaflet_markercluster/`
- `i18n/ar.po`, `i18n/ar_001.po`, `i18n/ab_ecommerce_storefront.pot`
- `tests/check_branches.cjs`
- `changelog.d/2026-10-12-branch-locator.md`
