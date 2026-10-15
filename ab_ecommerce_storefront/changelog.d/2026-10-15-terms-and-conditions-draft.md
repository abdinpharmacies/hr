# Terms and conditions draft for Egypt

## Recent relevant commit

Commit: `1d33b31ae9f8e11b16fea20aa7c924abdaf5b0a2`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: add return policy page`

- Add a dedicated return-policy page.

Files changed:

- `ab_ecommerce_storefront/views/legal_templates.xml`

## Current changes before commit:

- Add `/terms-and-conditions` with original English and Arabic draft wording for purchases in Egypt, covering accounts, orders, prices, pharmacy products, delivery, returns, privacy, complaints and future updates.
- Remove the highlighted draft-review banner and its dedicated styles at the user's request. Keep the existing terms text, sitemap exclusion and noindex response header.
- Add a section index, ten numbered sections, customer-support links, mobile layout, keyboard focus styles and RTL support using the existing brand styling.
- Link the page from the footer and product page. Replace the product page's generic 30-day guarantee and 2–3-day shipping copy with separate terms and returns links.
- Preserve the earlier removal of the product-page top assurance strip and all unrelated working changes.
- Add 53 translation entries and update references for four existing entries in the module POT and both Arabic catalogs, using an Odoo POT export.

Files changed for this draft:

- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/views/legal_templates.xml`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-15-terms-and-conditions-draft.md`

## Editorial references and review

- [Noon Egypt terms of sale](https://www.noon.com/egypt-en/terms-of-sale/) and [terms of use](https://www.noon.com/egypt-en/terms-of-use/): reference for topic structure, using indexed extracts because direct retrieval was unavailable. The draft is original wording, not copied terms or a statement of Noon's policies.
- [Egyptian Consumer Protection Agency FAQ](https://cpa.gov.eg/ar-eg/اسئلة-متكررة): reference for the distinction between ordinary returns with exceptions and defective-goods rights. Accessed 2026-10-15.
- Before approval, confirm the seller's legal identity, address and registration details; order-acceptance process; prescription verification; delivery areas and timing; cancellation/refund operations; and privacy arrangements.
- Reconcile the existing return-policy page with the approved wording, including its purchase-date trigger, blanket product exclusions and 21-business-day refund estimate. This task leaves that page's content unchanged.
- Add an effective date only after approval and then review the indexing settings. No live database upgrade or publication was performed.

## Validation

- Python AST, XML parsing, SCSS compilation, both `msgfmt --check-format` checks and scoped whitespace validation passed.
- Two targeted upgrades passed on the verified neutralized database `ecom19_product_ux_20261015`, with cron disabled and ports 5069/5072 configured; no user server was stopped.
- Before the banner removal, HTTP checks passed for English and Arabic titles, review notices, all ten sections and anchors, separate return links, Arabic RTL output, compiled frontend styles, and the separate return-policy route.
- The screenshot's product is unavailable in the isolated database. Existing published product `36441` passed verification for separate Arabic terms/return links and removal of the top strip.
- All 57 terms-page translation entries are present and non-fuzzy in both Arabic catalogs. Runtime Arabic was verified using the installed `ar_001` language.
- Browser visual verification was unavailable because this session exposes no browser. The isolated test filestore lacks some existing attachments; page HTML and newly compiled CSS were verified, but existing image assets were not.
- Validation scripts, exported POT and rendered HTML are in `/tmp/ab-terms-validation/`.
- After banner removal, XML parsing, the absence-of-banner check, SCSS compilation and both Arabic catalog format checks passed. No user-facing strings were added or changed, and existing translations were preserved.
- The targeted upgrade after banner removal passed on the same isolated database; log: `/tmp/ab-terms-validation/remove-notice-upgrade.log`. The live site was not upgraded.
