---
name: jaspr-testing
description: Write or run Jaspr component, server-rendering, and browser hydration tests with jaspr_test. Use when validating Jaspr behavior or fixing regressions.
---

# Jaspr verification

Inspect installed `jaspr_test`, existing tests, rendering mode, scripts, and browser support.
Check the installed test APIs before writing code: `testComponents`, `testServer`, and
`testClient` cover different environments and may require different imports or setup.
Do not copy Flutter's WidgetTester APIs into Jaspr tests.

Use focused component tests for rendering and events, server tests for HTML/data/status
behavior, and client/browser tests for DOM integration and hydration. Verify user-visible
results, lifecycle cleanup, and regression cases. Build request-specific fixtures; do not
reuse mutable server state across requests. Avoid tests that only mirror implementation.

Use the project's commands, `dart format` on changed sources, and `dart analyze` for the
Dart package. Run the nearest relevant tests and `jaspr build` when rendering/import or
asset boundaries change. Existing pure Dart skill guidance applies to shared logic; do
not add Flutter SDK dependencies or Flutter lints to a pure Jaspr package.
Report which environment was actually tested, including browser/build checks not available.
