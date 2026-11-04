# Recent commits

Author: Mohamed Fawzy
Date: 2026-11-04
Commit: 76e1336af5d884673ee565008dd2c140e78c3e6e
Subject: feat(ab_ecommerce_editor): add visual content studio with versioned publishing

- Add an animated content studio with staged entry, panel transitions, live draft preview, RTL, mobile canvas, and reduced-motion support.
- Add gentle independent floating motion to the library hero accent shapes, respecting reduced-motion preferences.
- Open the module menu directly on the normal content editor inside Odoo.
- Make the Abdin Studio brand section in the editor header the Open workspace / Close workspace control, animating the same editor into and out of full-screen mode without resetting its current document.
- Add three independent header controls for the tools rail, bottom recently deleted panel, and inspector, and show an expand/collapse indicator beside the Abdin Studio identity.
- Keep layer selection, drag ordering, and keyboard move controls in the tools rail; place recently deleted blocks in the bottom panel and translate its controls into both Arabic locales.
- Keep all three panel controls visible together on tablet widths and allow the tools, recently deleted, and inspector panels to be resized with pointer handles or arrow keys.
- Save each editor's panel visibility and dimensions in a module-owned, per-user layout record, with server-side ownership rules and fresh-install defaults.
- Add a per-user dark theme toggle for the editor and library while preserving the existing light theme as default and keeping the storefront preview in its authored colors.
- Style editor, library, rail, preview, and inspector scrollbars with the module's blue/violet colors and a slim rounded track.
- Add direct preview dragging with a visible drop marker and paired hop animations; synchronize preview/layers and preserve canvas nodes during reordering and undo/redo.
- Add animated library/editor exits.
- Place the Back control on the outer side of Save current changes in the editor header, keeping its unsaved-changes confirmation and pointing its arrow left in both languages.
- Enable Save current changes only while the editor has unsaved changes.
- Compare editable draft content with its saved snapshot so Save current changes disables again after reverting edits, undo, redo, or restored block styling, including reusable templates.
- Clear the selected block when clicking outside blocks and editing controls, returning the inspector to page settings.
- Arm a wide red delete border with a long press on a preview block, animate it out on deletion, and open Duplicate/Remove actions above the block on a quick double click.
- Keep removed blocks in a temporary, document-scoped bottom panel, with animated restoration to their prior position.
- Let editors drag a block from the preview or layer list into the bottom deleted-blocks panel, and drag a deleted block back into a chosen layer or preview position.
- Change the Arabic library headline to "صمم تجربتك" in both supported Arabic locales.
- Rename reusable content labels from قالب/قوالب to نموذج محتوى/نماذج المحتوى in both Arabic locales.
- Keep the library exit faded through the next render frame so opening a card does not briefly flash the library again.
- Place the live-preview message in the center of the canvas toolbar and remove its separate bottom strip.
- Let editors collapse the canvas toolbar with an upward chevron beside the page breadcrumb and reopen it from a compact downward tab above the preview; remember the choice per user.
- Create pages and articles using styled blocks, reusable templates, synchronized or detached sections, and undo/redo.
- Separate drafts from immutable published versions, with review, scheduled publication, restore, and publisher audit records.
- Add company-scoped editor roles, checked website assignments, safe image uploads, schema validation, and stale-save protection.
- Render editor-owned content inside the existing storefront and expose versioned JSON with compatibility fallback and conditional caching.
- Add complete English source strings and Arabic catalogs for ar and ar_001. Keep Flutter renderer integration deferred.

Files changed:

- `__init__.py`
- `__manifest__.py`
- `controllers/__init__.py`
- `controllers/editor_content.py`
- `data/scheduled_publish.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/editor_layout.py`
- `models/editor_document.py`
- `models/editor_template.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `security/security_groups.xml`
- `static/description/icon.svg`
- `static/schema/content-v1.json`
- `static/src/editor_public.scss`
- `static/src/editor_workspace.js`
- `static/src/editor_workspace.scss`
- `static/src/editor_workspace.xml`
- `views/editor_templates.xml`
- `views/editor_views.xml`

## Current changes before commit:

Author: Mohamed Fawzy
Date: 2026-11-04

- Document editor usage, publishing roles, routes, the JSON contract, and deferred Flutter integration.
- Record module-scoped interaction and motion requirements for future work.
- Record the initial implementation commit and distinguish prior runtime evidence from current static checks.
- Pre-commit checks passed Python parsing, XML/SVG and JSON parsing, manifest paths and developer ownership, JavaScript syntax, both SCSS compilations, and both Arabic catalogs with 282 translated entries each.
- Existing Node harnesses passed 20 dirty-state assertions and navigation exit, reduced-motion, and failed-load checks. Backend and browser suites were not rerun; the latest drag-to-trash interactions still need browser verification.

Files changed:

- `AGENTS.md`
- `README.md`
- `changelog.d/current.md`
