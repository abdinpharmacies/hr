---
name: odoo-translation
description: Add or repair English/Arabic Odoo translations using POT export, preserved PO entries and ar/ar_001 runtime verification.
---

Keep English literals in Python/XML/JS/Owl. Mark imperative strings with current
Odoo translation APIs (`self.env._`, `_`, JS `_t`); translate stable literal terms,
not already interpolated or dynamic expressions.

1. Identify every changed UI string and owning module. Inspect `i18n/ar.po`,
   `i18n/ar_001.po` and installed languages.
2. Follow [translation commands](references/workflow.md): targeted upgrade on an
   authorized development DB, then Odoo 19 POT export for accurate references.
3. Merge missing terms/references using a PO parser or reviewed gettext merge.
   Preserve existing `msgid`, translations and unrelated entries; no mass
   regeneration or deletion of either catalog.
4. Translate changed terms in both files, with `Language: ar` and `Language:
   ar_001` respectively. Check placeholders/plurals and changed fuzzy terms.
5. Run `msgfmt --check-format` on both catalogs, targeted upgrade/import as needed,
   then compare the same action/menu/view under `en_US` and `ar_001`. Verify actual
   differing text and Arabic frontend layout; language metadata alone is insufficient.

Never use `-u base`. For translatable SEO values, publish and verify each language
context; PO catalogs cover addon UI, not the whole editorial content lifecycle.
