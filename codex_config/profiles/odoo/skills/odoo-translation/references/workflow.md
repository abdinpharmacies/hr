# Translation Workflow

Verified with [Odoo 19 translations](https://www.odoo.com/documentation/19.0/developer/howtos/translations.html),
[CLI](https://www.odoo.com/documentation/19.0/developer/reference/cli.html) and local
`i18n export --help` on 2026-09-24.

First run the targeted module upgrade from the validation skill on an authorized
development DB, using correct addons paths and alternate ports. Export a fresh POT:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  --addons-path="$ODOO_ADDONS_PATH" i18n export \
  -c "$ODOO_CONFIG" -d "$ODOO_TEST_DB" \
  -l pot -o "/tmp/$ODOO_MODULE.pot" "$ODOO_MODULE"
```

The output option between `-l pot` and the module avoids ambiguous consumption of
the module by the language list. Export only the target module. This subcommand
does not need a second HTTP listener.

Merge terms/references into existing `i18n/ar.po` and `i18n/ar_001.po`, preferably
with the repository PO parser. A gettext `msgmerge` can provide a candidate in
`/tmp`, but review its diff and preserve unrelated translations/entries rather
than replacing catalogs wholesale. Do not rewrite stable `msgid` values. New
source strings need their own entries; retain old unrelated terms.

Each catalog needs valid gettext headers including Content-Type UTF-8 and the
correct Language (`ar` or `ar_001`). Preserve correct Arabic plural forms and
format placeholders; remove fuzzy flags only after translation review.

```bash
msgfmt --check-format -o /dev/null "$ODOO_MODULE/i18n/ar.po"
msgfmt --check-format -o /dev/null "$ODOO_MODULE/i18n/ar_001.po"
```

Upgrade only the target module again to load changes. If an existing translated
term requires explicit import/overwrite, scope that operation to this module and
language; do not globally overwrite translations. Never use `-u base`.

Verify an actual known action/menu/view under `with_context(lang='en_US')` and
`with_context(lang='ar_001')`, using an installed language and intended user.
Compare the same visible string and confirm the Arabic translation appears.
For frontend text inspect a browser with Arabic user context and ensure `_t`
literals are extracted and loaded. A catalog syntax pass is not runtime proof.

Keep source UI English; XML/QWeb text uses normal extraction, Python uses literal
translation calls, JS uses `_t` imported from `@web/core/l10n/translation`.
SEO translatable record values also require explicit per-language publication.
