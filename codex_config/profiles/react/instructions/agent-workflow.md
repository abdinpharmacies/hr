# Agent Workflow

- Inspect the existing code and its architecture before changing it; prefer editing existing files over creating new ones.
- Follow established conventions (framework, styling system, imports, naming); do not introduce a parallel style.
- Make small, incremental, focused changes; run the project's typecheck/lint/build to verify each step before moving on.
- Never guess APIs, import paths, or package versions — check the codebase or documentation first.
- Prefer the simplest fix that fits existing patterns; avoid extra dependencies and speculative abstraction.
- Ask the user when requirements are ambiguous or a change would be large, rather than assuming.
- Do not add code comments unless explicitly requested.
- Keep web-project work web-only: avoid React Native, mobile, or platform-specific patterns in React web code.
- Do not duplicate knowledge from skills into always-loaded rules; use skills and their references for detail.