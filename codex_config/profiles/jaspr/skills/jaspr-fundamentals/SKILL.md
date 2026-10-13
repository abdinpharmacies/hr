---
name: jaspr-fundamentals
description: Build or refactor Jaspr components and semantic HTML. Use for component composition, DOM parameters, events, state ownership, and browser access in Jaspr projects.
---

# Jaspr components

Inspect `pubspec.yaml`, the lockfile, rendering mode, and installed Jaspr sources first.
The bundled HTML signatures came from Jaspr 0.23.5; use the installed API when it differs.
Do not upgrade dependencies just to match an example.

Use `StatelessComponent` for presentation and `StatefulComponent` when local state is needed.
Modern Jaspr builds return one `Component`; use `Component.fragment` for multiple roots.
Use `.text`, `.fragment`, and `.empty` when Dart 3.10+ and the surrounding type support dot
shorthands; otherwise use the explicit `Component` factories. Do not introduce legacy
`Iterable<Component> build(...) sync*` into modern projects.

Import `package:jaspr/dom.dart` for typed HTML helpers. Children are usually a positional
list; prefer typed parameters and callbacks over raw attributes/events when supported.
Consult `references/html/<tag>.md` for the specific element, then confirm uncertain
signatures in installed source. Absence from this snapshot does not prove an API is absent.
Use `Component.element` when the installed version has no typed helper. In particular,
verify `style` versus `styles` instead of mixing snippets from different releases.

Extract meaningful reusable components into named classes in matching snake_case files.
Keep parents focused on composition and ownership. Prefer collection-if and collection-for.
Use native links for navigation, buttons for actions, associated labels for inputs,
keyboard focus, semantic headings, and useful image alternative text.

Use existing state management. Dispose owned subscriptions, effects, timers, and controllers.
Keep provider consumers below their provider: an outer build context cannot read a provider
that is only created in the returned subtree.

For browser access reachable from server rendering, use the compatible `universal_web`
imports and guard execution with `kIsWeb`; a runtime guard does not make a browser-only
import safe on the VM. Use `GlobalNodeKey` only when direct DOM access is needed.
Register global listeners after initialization and cancel them on disposal.

Read [rendering and hydration](../jaspr-pre-rendering-and-hydration/SKILL.md) for SSR/SSG,
[styling](../jaspr-styling/SKILL.md) for CSS, [interop](../jaspr-js-interop/SKILL.md) for JS,
and [HTML conversion](../jaspr-convert-html/SKILL.md) for migration tasks.
