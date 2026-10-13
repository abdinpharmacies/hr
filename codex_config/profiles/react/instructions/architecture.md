# Architecture

- Prefer small, single-responsibility components over monolithic files; extract reusable pieces into their own files.
- Prefer composition over configuration: avoid boolean-prop proliferation; use compound components with shared context when an API grows complex.
- Lift state only when genuinely shared between siblings; keep state local otherwise.
- Preserve the existing architecture when modifying code; review the codebase structure before adding new files.
- Avoid premature abstraction — extract a pattern only after it genuinely repeats.
- Do not introduce a dependency when existing utilities or platform APIs suffice.
- Follow the project's established conventions (file layout, naming, component API style).