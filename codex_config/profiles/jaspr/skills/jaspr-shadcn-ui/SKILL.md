---
name: jaspr-shadcn-ui
description: Build or troubleshoot Jaspr UI using shadcn_jaspr and its Tailwind theme pipeline when that library is installed or requested.
---

# shadcn_jaspr

Inspect the installed `shadcn_jaspr`, Jaspr, Dart, and Tailwind versions and the actual
component source. The collected upstream examples target an older library snapshot;
component counts, signatures, and build commands are not version guarantees.

Use the package barrel import and supported `Shad*` component families. Check the exact
constructor for positional versus named children, disabled flags, and callbacks. Keep
controlled values and uncontrolled defaults distinct. Compose subcomponents inside the
required scope for dialogs, menus, tabs, forms, and selectors.

Preserve CSS variables and the existing Tailwind pipeline. Ensure package sources are
scanned, theme CSS is loaded, and needed arbitrary variants survive compilation. Prefer
existing scripts or `jaspr_tailwind` integration when present; use a separate Tailwind
command only when that project's setup requires it. Verify missing classes in generated
CSS before adding an explicit source/safelist rule. Never edit compiled CSS directly.

For consumer apps, follow the app's component/file layout. Library-internal conventions
such as CVA helpers, `data-slot`, barrel exports, and family files apply when modifying the
library itself. Do not force them on every Jaspr project.

Verify keyboard interaction, focus restoration, labels, error messages, themes, narrow
viewports, and SSR/hydration for interactive components. Authentication blocks are UI;
connect them to the existing auth flow instead of treating them as authentication logic.
