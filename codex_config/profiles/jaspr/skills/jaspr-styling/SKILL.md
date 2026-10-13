---
name: jaspr-styling
description: Style Jaspr components with CSS-in-Dart or an existing CSS pipeline. Use for responsive layout, themes, selectors, and style API troubleshooting.
---

# Jaspr styling

Inspect the existing CSS pipeline and installed Jaspr API. Preserve Tailwind, external CSS,
or CSS-in-Dart when already established. The bundled property references are a Jaspr 0.23.5
snapshot; confirm mismatches against installed source.

For server/static projects using CSS-in-Dart, define static styles with `@css` on supported
top-level/static getters returning `List<StyleRule>`. Generated styles are global: scope
selectors with component classes. For client-only mode, use the installed version's
stylesheet mechanism; do not assume `@css` generation is available in that mode.
Use inline styles for values derived from state. Put media queries, pseudo classes, and
animations in stylesheet rules. Preserve the project entrypoint's stylesheet loading.

Use CSS flexbox/grid and media queries for responsive DOM layout. Check narrow and wide
viewports, long text, zoom, focus styles, and reduced-motion behavior when relevant.
Use typed properties supported by the installed version; use raw CSS only for unsupported
properties. Match the SDK before using dot shorthand. Rebuild the existing Tailwind/CSS
pipeline when adding classes; do not edit generated CSS.

Read only the needed bundled reference:

- [Sizing](references/sizing.md): units, dimensions, margin, padding, borders.
- [Color](references/color.md): color values.
- [Box](references/box.md): position, overflow, backgrounds, transforms.
- [Typography](references/typography.md): fonts and text.
- [Flexbox](references/flexbox.md): flex containers and items.
- [Grid](references/grid.md): tracks and placement.
- [Animation](references/animation.md): transitions and keyframes.
