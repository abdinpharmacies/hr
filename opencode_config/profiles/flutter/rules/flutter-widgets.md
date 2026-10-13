---
description: Flutter widget conventions: const constructors, StatelessWidget by default, semantic extraction, dedicated public widget files, model passing, and respecting the project architecture.
alwaysApply: true
---
# Flutter Widget Conventions

Follow Flutter widget structure and project layout conventions.

- Use `const` constructors wherever appropriate.
- Prefer `StatelessWidget`; use `StatefulWidget` only when state is required.
- Extract reusable UI into semantic widgets rather than inline widget trees.
- Model each reusable widget as a public class in its own dedicated file.
- Pass model objects instead of multiple primitives when appropriate.
- Respect the existing project architecture and layout convention.
