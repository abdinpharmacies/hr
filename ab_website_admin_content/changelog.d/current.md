Recent commits:

Commit: `0440f98`
Author: Mohamed Fawzy
Date: 2026-09-08 11:04:41 +0300
Subject: ab_website_admin_content/feat: add homepage carousel admin content

User-facing changes:

- Add the Website Content administration workspace.
- Add backend Homepage Carousel management for slide image, sequence, active state, optional content, CTA destination, CTA style, and visual CTA positioning.
- Add draggable and resizable CTA placement preview for homepage carousel slides.
- Add scoped modern styling for website pages, product pages, technical pages, and carousel administration screens.
- Add website-designer access and public/portal read rules for active carousel slides.
- Add Arabic translations for the module strings in both supported Arabic language files.

Files changed:

- `ab_website_admin_content/__init__.py`
- `ab_website_admin_content/__manifest__.py`
- `ab_website_admin_content/changelog.d/current.md`
- `ab_website_admin_content/i18n/ar.po`
- `ab_website_admin_content/i18n/ar_001.po`
- `ab_website_admin_content/models/__init__.py`
- `ab_website_admin_content/models/website_carousel_slide.py`
- `ab_website_admin_content/security/ir.model.access.csv`
- `ab_website_admin_content/security/record_rules.xml`
- `ab_website_admin_content/static/src/js/carousel_position_preview.js`
- `ab_website_admin_content/static/src/scss/content_admin.scss`
- `ab_website_admin_content/views/content_views.xml`

Current changes before commit:

- Redesign the Homepage Carousel action as a visual builder with kanban slide cards, a large live preview stage, structured content/image/CTA panels, and secondary advanced precision controls.
- Render slide title, subtitle, and full-banner link state inside the backend preview so admins see a closer representation of the storefront banner while editing.
- Keep the existing drag-and-resize CTA behavior, but improve the selected state and keep position/width values behind an Advanced Settings section.
- Add desktop/mobile preview sizing controls in the builder without changing frontend carousel behavior or stored data.
- Make CTA configuration contextual: show a no-CTA empty state, show only relevant text/image/link controls, and explain the full-banner link behavior in plain language.
- Add live preview updates for title and subtitle changes while preserving the existing field-backed Odoo form behavior.
- Remove the carousel slide kanban dynamic class interpolation so the Odoo 19 OWL template compiler can render the builder without a client-side error.
- Fix the Preview storefront action to use the Odoo 19 website preview URL helper instead of the removed `website.website_url` field.
- Change the builder top-bar Preview storefront control to a direct website preview link so admins can open the storefront without a form RPC call.
- Show the configured customer action type on carousel kanban cards so admins can identify Text Button, Image Button, Entire Banner, or No CTA before opening a slide.
- Fix the kanban customer-action condition to use OWL-compatible `!record.show_cta.raw_value` instead of Python-style `not`.
- Improve the selected Desktop/Mobile preview toggle colors so active options use a green background with readable dark text.
- Temporarily comment out the Desktop/Mobile preview toggle controls until the mobile preview behavior is fully tested.
- Add modern pharmacy admin styling for slide cards, builder panels, upload surfaces, preview copy, CTA handles, focus states, and responsive desktop layouts.
- Add Arabic translations for the new builder copy in both `ar.po` and `ar_001.po`.

Files changed:

- `ab_website_admin_content/changelog.d/current.md`
- `ab_website_admin_content/i18n/ar.po`
- `ab_website_admin_content/i18n/ar_001.po`
- `ab_website_admin_content/models/website_carousel_slide.py`
- `ab_website_admin_content/static/src/js/carousel_position_preview.js`
- `ab_website_admin_content/static/src/scss/content_admin.scss`
- `ab_website_admin_content/views/content_views.xml`
