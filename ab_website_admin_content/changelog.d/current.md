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

- Make the carousel Destination URL widget open the exact saved address, including a full HTTPS endpoint, and display the URL left to right in the Arabic editor.

Files changed:

- `ab_website_admin_content/views/content_views.xml`
- `ab_website_admin_content/changelog.d/current.md`
