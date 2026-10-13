---
description: Core engineering and code quality for Flutter/Dart: pragmatism, SRP, DRY, clear naming, type safety, immutable state, concise maintainable code.
alwaysApply: true
---
# Flutter Code Quality

Write pragmatic, clean, maintainable Flutter/Dart code.

- Build the simplest correct solution for the immediate need. Do not add speculative abstractions, layers, or patterns.
- Single Responsibility Principle: one clear responsibility per class, function, and file.
- DRY: extract duplicated logic into named constants, methods, or widgets.
- Use clear, descriptive, accurate names. Avoid meaningless names like `data`, `temp`, `manager`.
- Use the type system for safety; avoid unchecked `dynamic` and excessive casts.
- Prefer immutable state (`final`, `const`) where appropriate.
- Keep code concise; avoid unnecessary abstractions and over-engineering.
