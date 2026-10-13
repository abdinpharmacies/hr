# Jaspr profile

Build Dart web applications with Jaspr components and semantic HTML/CSS. Inspect the existing
project and respect its rendering mode, architecture, SDK constraints, and installed APIs.
The collected references contain different versions; installed source is authoritative for
signatures. Do not copy dependency pins or introduce framework upgrades to match examples.

Use `StatelessComponent` by default and stateful components only for local state. Extract
meaningful reusable UI into public component classes in matching snake_case files rather
than private component-returning helpers. Keep parent components thin and use const where
supported. Prefer typed immutable models, named actions, collection-if, and collection-for.
Keep server, shared Dart logic, and browser concerns separate only as the feature requires.

Jaspr UI uses DOM layout, not Flutter widgets. Do not apply Flutter layout, asset generation,
Navigator, or WidgetTester conventions to Jaspr. Use a supported embedding integration only
when Flutter embedding is requested. Keep identifiers stable; never persist runtime type names.

Use existing state management. Local state does not require a state library. BlocSignal and
Signals skills are available for projects using or explicitly adopting them; they do not
mandate a migration. Keep provider readers below providers and dispose owned resources.
Request-specific mutable state must not become server-global state.
