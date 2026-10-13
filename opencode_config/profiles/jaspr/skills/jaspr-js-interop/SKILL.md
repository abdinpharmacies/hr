---
name: jaspr-js-interop
description: Wrap JavaScript libraries or access browser APIs from Jaspr while preserving server/client import safety and resource disposal.
---

# Jaspr JavaScript interop

Inspect the installed Dart, Jaspr, and browser library versions. Use modern extension types
and `@JS` bindings supported by that SDK; do not copy legacy `package:js` annotations into
`dart:js_interop` declarations.

In server/static shared code, use compatible `universal_web/js_interop.dart` and
`universal_web/web.dart` imports and guard browser execution with `kIsWeb`. In client-only
code, use `dart:js_interop` and `package:web/web.dart`. Prefer typed browser bindings for
standard DOM APIs; use JS interop for external libraries and uncovered APIs.

Represent JS objects using extension types implementing `JSObject`, and use external
constructors/members with supported JS types. Convert Dart/JS values explicitly with the
installed interop conversion APIs. Handle asynchronous library loading before invoking it.
Retain callback identities when unregistering JS listeners, and dispose JS resources,
subscriptions, observers, and timers with the owning component.

Keep browser-only work inside hydrated interactive boundaries. Test both the browser path
and server/static build when shared code changes. Do not expose server credentials through
serialized props, JS globals, or generated assets.
