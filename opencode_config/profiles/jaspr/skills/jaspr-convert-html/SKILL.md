---
name: jaspr-convert-html
description: Convert existing HTML or a website section into Jaspr components while preserving the requested markup, CSS, assets, and behavior.
---

# HTML to Jaspr

Inspect the source HTML, target component structure, installed Jaspr CLI, and asset pipeline.
Use `jaspr convert-html --help` to verify available options, then prefer the converter:

```bash
jaspr convert-html --file path/to/source.html --query '#section'
jaspr convert-html --url https://example.com --query 'body > *'
```

Use a selector when only a section is requested. If the installed CLI lacks conversion,
report that limitation and use a scoped manual translation checked against the installed
DOM signatures; do not upgrade tooling silently.

Treat generated output as a starting point. Preserve tags, classes, IDs, attributes,
whitespace-sensitive content, and existing behavior required by the task. Check converter
output for incompatible APIs and unsupported event attributes. Preserve external JS when
doing a structure-only migration; implement behavior in Dart when the requested migration
includes replacing that JS. Do not leave attributes whose required runtime was removed.

Resolve assets through the target project's actual pipeline. Do not assume flutter.dev's
`asset()` helper or directory layout exists. Extract repeated content into typed inputs
and collection-for when it preserves output; use YAML or `jaspr_content` only if established
or needed. Compare rendered HTML and the relevant responsive/interactive states.
