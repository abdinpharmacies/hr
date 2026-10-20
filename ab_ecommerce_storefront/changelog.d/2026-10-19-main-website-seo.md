# Main website SEO and bilingual dashboard text

Current changes before commit:
- Add English and Arabic native SEO titles, descriptions, and keywords for the homepage, shop, about, contact, branches, prescription request, business enquiries, returns, and offers pages.
- Add Organization and WebSite microdata and a visible contact heading. Keep one main H1 on the homepage and shop.
- Remove the added homepage introduction at the user's request on 2026-10-20. Use the existing pharmacy essentials heading as the homepage H1 with its original appearance, preserving native SEO metadata and both languages.
- Add the public `/offers` landing page and connect the homepage and navigation links to it. Empty offers pages are marked noindex.
- Canonicalize the unscoped category listing to `/shop`, retain localized canonical and alternate language links, and exclude account, authentication, checkout, order tracking, and filtered search pages from indexing.
- Exclude order tracking from the generated sitemap. Preserve editorial metadata on subsequent module upgrades with initialization-only defaults.
- Preserve all 1,908 pre-task entries in each Arabic catalog, append 41 terms, correct three untranslated labels, and merge current Odoo references and code translation markers.

Validation:
- Targeted upgrade of `ab_ecommerce_storefront` passed on neutralized database `ecom19_seo_20261019`; validation HTTP/gevent ports were 5069/5072.
- Twenty-five HTTP cases passed on both the isolated copy and the live LAN website on port 4092, covering nine pages in both languages, indexing rules, canonical URLs, hreflang, headings, structured data, and sitemap entries.
- Both catalogs passed `msgfmt --check-format`. XML parsing, manifest load order, translation preservation, and `git diff --check` passed.
- Verified coverage of 1,698 exported terms, including 160 frontend terms and 304 Python terms. Six admin menu/action names and three customer dashboard templates differed correctly between English and Arabic in both databases.
- Applied only the reviewed SEO XML, native metadata, and module Arabic translations to `ecom19` through Odoo ORM after a database backup. Used Odoo's native website-specific view propagation and invalidated generated sitemap attachments.
- Refreshed the three HTTP workers gracefully, one at a time, to load code translations. The main Odoo process remained running. The live translation endpoint returned the corrected frontend messages with no missing exported terms.
- The isolated copy retained unrelated existing registry/view warnings and did not contain the source filestore. Browser visual checks were unavailable because the session had no connected browser.
- No inventory, pricing, order, external database, or access-rule changes were included in this work. No full module upgrade was run on `ecom19`.
- On 2026-10-20, the targeted replica upgrade and both-language ORM checks passed for removing the introduction. Only the homepage SEO view and its translated website-specific copy were updated on `ecom19`; title and description values were verified unchanged.
- Live English and Arabic homepage checks passed after removal, including the existing H1, preserved metadata and structured data, and compiled heading styles.

Production configuration:
- The LAN URL on port 4092 remains the testing address. Set the website domain to the final HTTPS URL before public launch, then verify canonical URLs, language alternatives, sitemap, and search-engine ownership on that domain.
- The reviewed metadata is stored in Odoo's native fields and remains editable with Optimize SEO in each website language.
- Keep validation scripts, database backups, tests, and generated caches outside the production addon package.

Files changed:
- `__manifest__.py`
- `views/seo.xml`
- `data/seo_metadata.xml`
- `static/src/scss/storefront.scss`
- `i18n/ab_ecommerce_storefront.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-19-main-website-seo.md`

Relevant commit:
- Commit: `10f6613082109d49f4012280273d7673aa454f4d`
- Author: Mohamed Fawzy
- Date: 2026-10-15
- Original subject: `ab_ecommerce_storefront/IMP: add review carousel navigation and image previews`
- Added customer review navigation and image previews to the homepage.
- Files changed (relevant): `__manifest__.py`, `views/homepage.xml`, `i18n/ab_ecommerce_storefront.pot`, `i18n/ar.po`, `i18n/ar_001.po`.
