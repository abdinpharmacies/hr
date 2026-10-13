---
name: jaspr-pre-rendering-and-hydration
description: Implement or debug Jaspr static/server rendering, async data fetching, client boundaries, hydration, and server/client entrypoint separation.
---

# Rendering and hydration

Read the project's `jaspr.mode`, entrypoints, generated options, and installed version.
Static mode renders at build time; server mode renders per request; client mode runs in the
browser. Preserve the chosen mode unless changing it is part of the task.

In server/static mode, use the established server entrypoint and generated initialization.
Keep `ClientApp()` and client options initialization consistent with the installed template.
Do not edit generated options files or wrap `ClientApp` in extra DOM elements.
Annotate the uppermost interactive subtree with `@client`; descendants are included.
An annotated component also executes during pre-rendering, so browser calls still need guards.

Keep `dart:io`, FFI, database clients, and secrets out of the client import graph. Keep
`dart:js_interop` and browser-only libraries out of the server import graph. For shared DOM
access, use compatible `universal_web` imports and guard execution with `kIsWeb`, or use
conditional imports supported by the project. Do not merely guard an incompatible import.

Pass serializable public initial values across client boundaries. Use supported encoders
and decoders for custom types. Verify the installed version's slot/child support before
passing component children; ordinary callbacks are not serializable constructor data.
Keep initial server/client markup deterministic. Avoid time, random values, browser width,
and browser storage changing the initial tree before hydration.

For server-side async loading, use the installed server async components such as
`AsyncStatelessComponent` or `AsyncBuilder`. Pass fetched data into the interactive subtree
rather than duplicating the initial fetch. Keep request-specific state scoped per request.

For hydration bugs, inspect initial HTML, generated assets/options, console errors, and
import boundaries. Verify meaningful HTML before scripts and interaction afterward.
Run the mode-appropriate build and focused server/client tests; a successful Dart analysis
alone does not verify hydration.
