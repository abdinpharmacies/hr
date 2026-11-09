---
name: odoo-translation
description: Add or repair English/Arabic Odoo translations using POT export, preserved PO entries and ar/ar_001 runtime verification.
---

Keep English literals in Python/XML/JS/Owl. Mark imperative strings with current
Odoo translation APIs (`self.env._`, `_`, JS `_t`); translate stable literal terms,
not already interpolated or dynamic expressions.

## Translate automatically within the task scope

When a task adds or changes user-facing text, complete its English source and both
Arabic catalogs as part of the task. Do not ask for separate translation approval
or confirmation of the module list when the scope is clear from the user's request
and the affected code. The same applies to explicitly requested translation fixes.

Inspect the affected code to identify the owning modules and translate only terms
needed for the requested work, including necessary Python/XML/JS translation fixes.
Briefly report the affected modules as a progress update; this is not an approval
gate. Preserve the user's module exclusions and unrelated existing changes.

Do not translate whole modules, installed dependencies, or other matching terms
merely because they are available. If task-related text belongs to another module,
make only the necessary translation changes there and explain its ownership. Ask
only when the intended scope is genuinely ambiguous or conflicts with an explicit
exclusion; continue independent work within the clear scope.

Automatic translation does not authorize deployment, publication, or changes to an
unauthorized database. Keep all translation validation requirements below.

## Translation workflow

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
